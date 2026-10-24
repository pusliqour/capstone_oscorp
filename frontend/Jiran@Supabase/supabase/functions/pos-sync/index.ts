import { serve } from "https://deno.land/std/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const APIDECK_API_KEY = Deno.env.get("APIDECK_API_KEY")!;
const APIDECK_APP_ID = Deno.env.get("APIDECK_APP_ID")!;

type Json = Record<string, any>;

serve(async (req) => {
  const cors = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers":
      "authorization, x-client-info, apikey, content-type",
  };
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });

  const supabase = createClient(SUPABASE_URL, SERVICE_ROLE_KEY);

  try {
    const payload = await req.json().catch(() => ({}) as Json);
    const retailerId: string | null = payload?.retailer_id ?? null;
    if (!retailerId)
      return new Response(JSON.stringify({ error: "Missing retailer_id" }), {
        status: 400,
        headers: { ...cors, "Content-Type": "application/json" },
      });

    // Find active Square connection
    const { data: conn, error: connErr } = await supabase
      .from("pos_connections")
      .select("id, consumer_id, provider")
      .eq("retailer_id", retailerId)
      .eq("is_active", true)
      .single();

    if (connErr || !conn)
      return new Response(
        JSON.stringify({ error: "No active Square connection" }),
        {
          status: 404,
          headers: { ...cors, "Content-Type": "application/json" },
        },
      );

    const connectionId = conn.id;
    const consumerId = conn.consumer_id;
    const provider = conn.provider;

    if (provider !== "square") {
      console.log("Active provider is not square. Skipping sync.");
      return new Response(
        JSON.stringify({ message: "Manual mode active. POS sync skipped." }),
        {
          status: 200,
          headers: { ...cors, "Content-Type": "application/json" },
        },
      );
    }

    let nextUrl: string | null =
      "https://unify.apideck.com/pos/items?limit=200";
    const now = new Date().toISOString();
    let total = 0;

    // ----------- 🔥 Fetch Square Catalog (Items + Categories) via Proxy -----------
    const categoryMap = new Map<string, string>();
    const itemCategoryMap = new Map<string, string | null>();

    try {
      const catalogRes = await fetch("https://unify.apideck.com/proxy", {
        method: "POST",
        headers: {
          "x-apideck-app-id": APIDECK_APP_ID,
          "x-apideck-consumer-id": consumerId,
          "x-apideck-service-id": "square",
          "x-apideck-downstream-url":
            "https://connect.squareup.com/v2/catalog/search",
          "Content-Type": "application/json",
          Authorization: `Bearer ${APIDECK_API_KEY}`,
        },
        body: JSON.stringify({
          object_types: ["CATEGORY", "ITEM"],
        }),
      });

      const catalogJson = await catalogRes.json().catch(() => ({}));

      if (catalogRes.ok && Array.isArray(catalogJson?.objects)) {
        for (const obj of catalogJson.objects) {
          if (obj.type === "CATEGORY") {
            // Map Category ID -> Name
            categoryMap.set(obj.id, obj.category_data?.name ?? "Uncategorized");
          } else if (obj.type === "ITEM") {
            const itemId = obj.id;

            // NEW FIX: Square now uses an array of categories
            // We take the first category ID from the array if it exists
            const categories = obj.item_data?.categories;
            const categoryId =
              Array.isArray(categories) && categories.length > 0
                ? categories[0].id
                : (obj.item_data?.category_id ?? null); // Fallback to old field just in case

            itemCategoryMap.set(itemId, categoryId);
          }
        }
        console.log(
          `Verified: ${categoryMap.size} categories, ${itemCategoryMap.size} items linked.`,
        );
      }
    } catch (catErr) {
      console.error("Catalog fetch error:", catErr);
    }
    // ----------- 🔥 END catalog fetch -----------

    // ----------- 1️⃣ Fetch and upsert staging tables -----------
    while (nextUrl) {
      const res = await fetch(nextUrl, {
        method: "GET",
        headers: {
          "x-apideck-app-id": APIDECK_APP_ID,
          "x-apideck-consumer-id": consumerId,
          Authorization: `Bearer ${APIDECK_API_KEY}`,
        },
      });

      const json = await res.json();

      if (!res.ok) {
        await supabase
          .from("pos_connections")
          .update({ last_error: JSON.stringify(json), updated_at: now })
          .eq("id", connectionId);
        return new Response(
          JSON.stringify({ error: "Apideck error", details: json }),
          {
            status: 502,
            headers: { ...cors, "Content-Type": "application/json" },
          },
        );
      }

      const items: any[] = json?.data ?? [];
      total += items.length;

      const itemsRows = items.map((it) => ({
        id: it.id,
        pos_connection_id: connectionId,
        name: it.name ?? null,
        description: it.description ?? null,
        product_type: it.product_type ?? null,
        present_at_all_locations: !!it.present_at_all_locations,
        deleted: !!it.deleted,
        version: it.version ?? null,
        last_seen_at: now,
        updated_at: now,
      }));

      if (itemsRows.length)
        await supabase
          .from("pos_catalog_items")
          .upsert(itemsRows, { onConflict: "pos_connection_id,id" });

      const variationsRows = items.flatMap((it) =>
        (it.variations ?? []).map((v: any) => ({
          id: v.id,
          pos_connection_id: connectionId,
          item_id: it.id,
          name: v.name ?? null,
          pricing_type: v.pricing_type ?? null,
          price_amount: Number.isFinite(v.price_amount) ? v.price_amount : null,
          price_currency: v.price_currency ?? null,
          price: Number.isFinite(v.price_amount)
            ? v.price_amount / 100.0
            : null,
          currency: v.price_currency ?? null,
          deleted: !!v.deleted,
          is_active: !v.deleted,
          last_seen_at: now,
          updated_at: now,
        })),
      );

      if (variationsRows.length)
        await supabase
          .from("pos_catalog_variations")
          .upsert(variationsRows, { onConflict: "pos_connection_id,id" });

      nextUrl = json?.links?.next ?? null;
    }

    // ----------- Fetch and upsert POS locations -----------
    let locNextUrl: string | null = "https://unify.apideck.com/pos/locations";

    while (locNextUrl) {
      const locRes = await fetch(locNextUrl, {
        method: "GET",
        headers: {
          "x-apideck-app-id": APIDECK_APP_ID,
          "x-apideck-consumer-id": consumerId,
          Authorization: `Bearer ${APIDECK_API_KEY}`,
        },
      });

      const locJson = await locRes.json().catch(() => ({}));
      console.log("locations status:", locRes.status);
      console.log("locations body:", JSON.stringify(locJson));

      if (!locRes.ok) {
        await supabase
          .from("pos_connections")
          .update({ last_error: JSON.stringify(locJson), updated_at: now })
          .eq("id", connectionId);

        return new Response(
          JSON.stringify({
            error: "Apideck locations fetch error",
            details: locJson,
          }),
          {
            status: 502,
            headers: { ...cors, "Content-Type": "application/json" },
          },
        );
      }

      const locs: any[] = locJson?.data ?? [];

      const rows = locs.map((l: any) => ({
        id: l.id,
        pos_connection_id: connectionId,
        name: l.name ?? null,
        address: l?.address?.line1 ?? l?.address ?? null,
        city: l?.address?.city ?? null,
        country: l?.address?.country ?? null,
        timezone: l?.timezone ?? null,
        created_at: now,
      }));

      if (rows.length) {
        await supabase.from("pos_locations").upsert(rows, {
          onConflict: "pos_connection_id,id",
        });
      }

      locNextUrl = locJson?.links?.next ?? null;
    }

    // ----------- 2️⃣ Soft-deactivate missing staging rows -----------
    await supabase
      .from("pos_catalog_items")
      .update({ deleted: true, updated_at: now })
      .eq("pos_connection_id", connectionId)
      .lt("last_seen_at", now);

    await supabase
      .from("pos_catalog_variations")
      .update({ deleted: true, is_active: false, updated_at: now })
      .eq("pos_connection_id", connectionId)
      .lt("last_seen_at", now);

    // ----------- 2️⃣b Fetch and upsert inventory levels -----------
    // let invNextUrl: string | null = "https://unify.apideck.com/pos/inventory_levels";
    // let inventoryTotal = 0;

    // while (invNextUrl) {
    //   const invRes = await fetch(invNextUrl, {
    //     method: "GET",
    //     headers: {
    //       "x-apideck-app-id": APIDECK_APP_ID,
    //       "x-apideck-consumer-id": consumerId,
    //       Authorization: `Bearer ${APIDECK_API_KEY}`
    //     }
    //   });

    //   const invJson = await invRes.json();
    //   console.log("inventory_levels status:", invRes.status);
    //   console.log("inventory_levels body:", JSON.stringify(invJson));
    //   if (!invRes.ok) {
    //     await supabase.from("pos_connections").update({ last_error: JSON.stringify(invJson), updated_at: now }).eq("id", connectionId);
    //     return new Response(JSON.stringify({ error: "Apideck inventory fetch error", details: invJson }), { status: 502, headers: { ...cors, "Content-Type": "application/json" } });
    //   }

    //   const invItems: any[] = invJson?.data ?? [];
    //   console.log("Inventory response:", JSON.stringify(invJson, null, 2));
    //   console.log("Inventory items count:", invItems.length);
    //   inventoryTotal += invItems.length;

    //   // Map to pos_inventory_levels staging table
    //   const inventoryRows = invItems.map((lvl: any) => ({
    //     pos_connection_id: connectionId,
    //     pos_variation_id: lvl.variation_id,
    //     pos_location_id: lvl.location_id,
    //     quantity: Number.isFinite(lvl.quantity) ? lvl.quantity : 0,
    //     last_seen_at: now,
    //     updated_at: now
    //   }));

    //   if (inventoryRows.length) {
    //     await supabase
    //       .from("pos_inventory_levels")
    //       .upsert(inventoryRows, { onConflict: "pos_connection_id,pos_variation_id,pos_location_id" });
    //   }

    //   invNextUrl = invJson?.links?.next ?? null;
    // }

    // ----------- 2️⃣c Soft-deactivate missing inventory rows -----------
    // await supabase
    //   .from("pos_inventory_levels")
    //   .update({ quantity: 0, updated_at: now })
    //   .eq("pos_connection_id", connectionId)
    //   .lt("last_seen_at", now);

    // ----------- 2️⃣d Push staging → internal product_inventory -----------
    // const { data: stagingInv } = await supabase
    //   .from("pos_inventory_levels")
    //   .select("*")
    //   .eq("pos_connection_id", connectionId);

    // for (const lvl of stagingInv ?? []) {
    //   // Lookup internal product_variation_id
    //   const { data: variation, error: varErr } = await supabase
    //   .from("product_variations")
    //   .select("id")
    //   .eq("pos_connection_id", connectionId)
    //   .eq("pos_variation_id", lvl.pos_variation_id)
    //   .maybeSingle();

    // if (varErr) console.error("Variation lookup error:", varErr);
    // if (!variation) {
    //   console.warn("Missing product_variation for inventory:", lvl.pos_variation_id);
    //   continue;
    // }

    //   if (!variation) {
    //     console.warn("Missing product_variation for inventory:", lvl.pos_variation_id);
    //     continue;
    //   }

    //   // Upsert into product_inventory
    //   const { error } = await supabase.from("product_inventory").upsert(
    //     {
    //       product_variation_id: variation.id,
    //       pos_connection_id: connectionId,
    //       pos_location_id: lvl.pos_location_id,
    //       quantity: lvl.quantity,
    //       updated_at: now
    //     },
    //     { onConflict: "product_variation_id,pos_connection_id,pos_location_id" }
    //   );

    //   if (error) console.error("Product_inventory upsert error:", error);
    // }
    // ----------- 3️⃣ Push staging → internal tables safely -----------

    // 3A️⃣ Publish Products

    const { data: catalogItems } = await supabase
      .from("pos_catalog_items")
      .select("*")
      .eq("pos_connection_id", connectionId);

    for (const item of catalogItems ?? []) {
      const categoryId = itemCategoryMap.get(item.id) ?? null;
      const resolvedCategory =
        categoryId && categoryMap.has(categoryId)
          ? categoryMap.get(categoryId)
          : "Uncategorized"; // fallback if missing

      const { error } = await supabase.from("products").upsert(
        {
          pos_item_id: item.id,
          pos_connection_id: connectionId,
          retailer_id: retailerId,
          name: item.name,
          category: resolvedCategory,
          active: !item.deleted,
          updated_at: now,
        },
        { onConflict: "pos_connection_id,pos_item_id" },
      );

      if (error) console.error("Product upsert error:", error);
    }

    // 3B️⃣ Publish Variations
    const { data: catalogVars } = await supabase
      .from("pos_catalog_variations")
      .select("*")
      .eq("pos_connection_id", connectionId);

    for (const v of catalogVars ?? []) {
      // Find internal product ID
      const { data: product } = await supabase
        .from("products")
        .select("id")
        .eq("pos_connection_id", connectionId)
        .eq("pos_item_id", v.item_id)
        .single();

      if (!product) {
        console.warn("Missing product for variation:", v.id);
        continue;
      }

      const { error } = await supabase.from("product_variations").upsert(
        {
          pos_variation_id: v.id,
          pos_connection_id: connectionId,
          product_id: product.id,
          name: v.name,
          sku: v.id,
          price: v.price,
          currency: v.currency,
          active: v.is_active,
          updated_at: now,
        },
        { onConflict: "pos_connection_id,pos_variation_id" },
      );

      if (error) console.error("Variation upsert error:", error);
    }

    // ----------- 3C️⃣ Inventory sync (Square via Apideck Proxy) -----------
    const { data: stageVars } = await supabase
      .from("pos_catalog_variations")
      .select("id")
      .eq("pos_connection_id", connectionId)
      .is("is_active", true);

    const variationIds = (stageVars ?? []).map((v) => v.id);
    const { data: locs } = await supabase
      .from("pos_locations")
      .select("id")
      .eq("pos_connection_id", connectionId)
      .eq("deleted", false);

    let locationIds = (locs ?? []).map((l) => l.id);

    if (variationIds.length && locationIds.length) {
      const downstreamUrl =
        "https://connect.squareup.com/v2/inventory/batch-retrieve-counts";
      // OPTIMIZATION: Maximize chunk size to 1000 to reduce total calls
      const chunkSize = 1000;

      for (let i = 0; i < variationIds.length; i += chunkSize) {
        const chunk = variationIds.slice(i, i + chunkSize);
        const proxyRes = await fetch("https://unify.apideck.com/proxy", {
          method: "POST",
          headers: {
            "x-apideck-app-id": APIDECK_APP_ID,
            "x-apideck-consumer-id": consumerId,
            "x-apideck-service-id": "square",
            "x-apideck-downstream-url": downstreamUrl,
            "Content-Type": "application/json",
            Authorization: `Bearer ${APIDECK_API_KEY}`,
          },
          body: JSON.stringify({
            catalog_object_ids: chunk,
            location_ids: locationIds,
          }),
        });

        const proxyJson = await proxyRes.json().catch(() => ({}));

        if (!proxyRes.ok) {
          // If error contains invalid location IDs, filter them out and retry
          const invalidLocations: string[] = [];
          if (proxyJson?.errors) {
            for (const err of proxyJson.errors) {
              if (
                err.code === "NOT_FOUND" &&
                err.detail?.includes("location with the ID")
              ) {
                const idMatch = err.detail.match(/ID `(\w+)`/);
                if (idMatch) invalidLocations.push(idMatch[1]);
              }
            }
          }

          if (invalidLocations.length) {
            console.warn("Skipping invalid locations:", invalidLocations);
            // Remove invalid IDs and retry
            locationIds = locationIds.filter(
              (id) => !invalidLocations.includes(id),
            );
            if (!locationIds.length) {
              console.log(
                "No valid locations left, skipping remaining inventory sync.",
              );
              break;
            }
            i -= chunkSize; // retry same chunk with filtered locations
            continue;
          }

          console.error("Inventory proxy error:", proxyRes.status, proxyJson);
          await supabase
            .from("pos_connections")
            .update({ last_error: JSON.stringify(proxyJson), updated_at: now })
            .eq("id", connectionId);
          break; // give up if unknown error
        }

        const counts: any[] = proxyJson?.counts ?? [];

        // 1) rows that Square returned
        const rows = counts.map((c: any) => ({
          pos_connection_id: connectionId,
          pos_variation_id: c.catalog_object_id,
          pos_location_id: c.location_id,
          quantity: Number.isFinite(parseFloat(c.quantity))
            ? parseFloat(c.quantity)
            : 0,
          last_seen_at: now,
          updated_at: now,
        }));

        // 2) build a set of pairs that were returned
        const seen = new Set<string>();
        for (const c of counts) {
          if (!c?.catalog_object_id || !c?.location_id) continue;
          seen.add(`${c.catalog_object_id}__${c.location_id}`);
        }

        // 3) add missing (variation × location) as zero rows
        const zeroRows: any[] = [];
        for (const varId of chunk) {
          for (const locId of locationIds) {
            const key = `${varId}__${locId}`;
            if (seen.has(key)) continue;

            zeroRows.push({
              pos_connection_id: connectionId,
              pos_variation_id: varId,
              pos_location_id: locId,
              quantity: 0,
              last_seen_at: now,
              updated_at: now,
            });
          }
        }

        // 4) upsert all at once
        const allRows = [...rows, ...zeroRows];

        if (allRows.length) {
          const { error: upErr } = await supabase
            .from("pos_inventory_levels")
            .upsert(allRows, {
              onConflict: "pos_connection_id,pos_variation_id,pos_location_id",
            });

          if (upErr) console.error("pos_inventory_levels upsert error:", upErr);
        }

        console.log(
          `Inventory chunk done: ${i} → ${i + chunk.length}, returned=${rows.length}, zeros_added=${zeroRows.length}, total_upsert=${allRows.length}`,
        );

        console.log(
          `Inventory chunk done: ${i} → ${i + chunk.length}, rows=${rows.length}`,
        );
      }

      // Soft-deactivate inventory rows not seen in this sync
      await supabase
        .from("pos_inventory_levels")
        .update({ quantity: 0, updated_at: now })
        .eq("pos_connection_id", connectionId)
        .lt("last_seen_at", now);
    }
    // ----------- 3D️⃣ Push pos_inventory_levels -> product_inventory -----------

    // 1) Load all internal variation ids for this connection (pos_variation_id -> product_variations.id)
    const { data: pvRows, error: pvErr } = await supabase
      .from("product_variations")
      .select("id, pos_variation_id")
      .eq("pos_connection_id", connectionId);

    if (pvErr) console.error("product_variations map fetch error:", pvErr);

    const pvMap = new Map<string, string>();
    (pvRows ?? []).forEach((r: any) => {
      if (r?.pos_variation_id && r?.id) pvMap.set(r.pos_variation_id, r.id);
    });

    // 2) Read staging inventory for this connection
    const { data: invRows, error: invErr } = await supabase
      .from("pos_inventory_levels")
      .select("pos_variation_id, pos_location_id, quantity")
      .eq("pos_connection_id", connectionId);

    if (invErr) console.error("pos_inventory_levels fetch error:", invErr);

    const toUpsert: any[] = [];

    for (const lvl of invRows ?? []) {
      const internalVarId = pvMap.get(lvl.pos_variation_id);
      if (!internalVarId) {
        console.warn(
          "No internal product_variation for pos_variation_id:",
          lvl.pos_variation_id,
        );
        continue;
      }

      toUpsert.push({
        product_variation_id: internalVarId,
        pos_connection_id: connectionId,
        pos_location_id: lvl.pos_location_id,
        quantity: lvl.quantity ?? 0,
        updated_at: now,
      });
    }

    // 3) Upsert into product_inventory (conflict target uses the unique index you added)
    if (toUpsert.length) {
      const { error: piErr } = await supabase
        .from("product_inventory")
        .upsert(toUpsert, {
          onConflict: "product_variation_id,pos_connection_id,pos_location_id",
        });

      if (piErr) console.error("product_inventory upsert error:", piErr);
    }

    console.log("product_inventory upserted rows:", toUpsert.length);

    // ✅ Guard: if user switched away from Square while sync is running,
    // DO NOT publish orders into the frontend tables.
    const { data: stillActiveConn, error: stillActiveErr } = await supabase
      .from("pos_connections")
      .select("id, provider, is_active")
      .eq("retailer_id", retailerId)
      .eq("is_active", true)
      .maybeSingle();

    if (stillActiveErr) {
      console.error("Active-connection recheck failed:", stillActiveErr);
    } else {
      const stillActive =
        stillActiveConn &&
        stillActiveConn.is_active === true &&
        stillActiveConn.provider === "square" &&
        stillActiveConn.id === connectionId;

      if (!stillActive) {
        console.log(
          "Skipping orders publish: connection is no longer the active Square connection.",
          { stillActiveConn, connectionId },
        );

        // still mark connection time if you want, or just exit cleanly:
        return new Response(
          JSON.stringify({ ok: true, skipped_orders: true }),
          {
            status: 200,
            headers: { ...cors, "Content-Type": "application/json" },
          },
        );
      }
    }

    // ----------- 5️⃣ OPTIMIZED: Fetch POS orders in ONE call for ALL locations -----------
    let ordersTotal = 0;
    let ordersInserted = 0;

    if (locationIds.length > 0) {
      // OPTIMIZATION: Send all location IDs in one body to avoid per-location loops
      const body = {
        location_ids: locationIds,
        return_entries: true,
        limit: 500, // Increased limit to capture more orders per call
        query: {
          filter: { state_filter: { states: ["COMPLETED"] } },
          sort: { sort_field: "CLOSED_AT", sort_order: "DESC" },
        },
      };

      const ordersRes = await fetch("https://unify.apideck.com/proxy", {
        method: "POST",
        headers: {
          "x-apideck-app-id": APIDECK_APP_ID,
          "x-apideck-consumer-id": consumerId,
          "x-apideck-service-id": "square",
          "x-apideck-downstream-url":
            "https://connect.squareup.com/v2/orders/search",
          "Content-Type": "application/json",
          Authorization: `Bearer ${APIDECK_API_KEY}`,
        },
        body: JSON.stringify(body),
      });

      const ordersJson = await ordersRes.json().catch(() => ({}));

      if (ordersRes.ok) {
        const orders = ordersJson?.data ?? [];
        ordersTotal = orders.length;

        const { data: validVars } = await supabase
          .from("pos_catalog_variations")
          .select("id")
          .eq("pos_connection_id", connectionId);

        const validVarSet = new Set((validVars ?? []).map((v) => v.id));

        const orderRows = orders
          .flatMap((order) =>
            (order.line_items ?? []).map((li: any) => {
              const varId = li.variation_id ?? null;
              if (varId && !validVarSet.has(varId)) return null;
              return {
                id: order.id,
                pos_connection_id: connectionId,
                pos_location_id: order.location_id ?? null,
                pos_variation_id: varId,
                item_name: li.name ?? null,
                quantity: Number(li.quantity) ?? 0,
                total_amount: Number(li.total_money?.amount ?? 0) / 100.0,
                currency: li.total_money?.currency ?? null,
                order_time: order.created_at ?? now,
                created_at: now,
                updated_at: now,
              };
            }),
          )
          .filter(Boolean);

        if (orderRows.length) {
          await supabase.from("pos_orders").upsert(orderRows, {
            onConflict: "id,pos_connection_id,pos_variation_id",
          });
          ordersInserted = orderRows.length;
        }
      }

      console.log(
        `POS orders fetched: ${ordersTotal}, orders inserted/updated: ${ordersInserted}`,
      );
    }

    // ----------- 6️⃣ Publish POS orders -> frontend orders (HEADERS ONLY) -----------

    const { data: posLines, error: posLinesErr } = await supabase
      .from("pos_orders")
      .select("id, pos_location_id, order_time, total_amount, currency")
      .eq("pos_connection_id", connectionId);

    if (posLinesErr) {
      console.error("pos_orders read error (publish headers):", posLinesErr);
    } else {
      // Build 1 order header per Square order id (pos_orders.id)
      // Choose: earliest order_time, sum total_amount across lines (safe because your pos_orders total_amount is line total)
      const orderMap = new Map<string, any>();

      for (const line of posLines ?? []) {
        const extOrderId = line.id; // Square order id
        if (!extOrderId) continue;

        const existing = orderMap.get(extOrderId);

        const lineTime = line.order_time
          ? new Date(line.order_time).toISOString()
          : now;
        const lineTotal = Number(line.total_amount ?? 0);
        const lineCurrency = line.currency ?? null;

        if (!existing) {
          orderMap.set(extOrderId, {
            retailer_id: retailerId,
            source: "square",
            pos_connection_id: connectionId,
            external_order_id: extOrderId,
            external_location_id: line.pos_location_id ?? null,
            status: "completed",
            order_time: lineTime,
            total_amount: lineTotal,
            currency: lineCurrency,
            updated_at: now,
          });
        } else {
          // keep earliest order_time
          if (
            existing.order_time &&
            lineTime &&
            lineTime < existing.order_time
          ) {
            existing.order_time = lineTime;
          }
          // sum totals across lines
          existing.total_amount =
            Number(existing.total_amount ?? 0) + lineTotal;

          // keep a currency if missing
          if (!existing.currency && lineCurrency)
            existing.currency = lineCurrency;

          // prefer a location if missing
          if (!existing.external_location_id && line.pos_location_id) {
            existing.external_location_id = line.pos_location_id;
          }

          existing.updated_at = now;
          orderMap.set(extOrderId, existing);
        }
      }

      const ordersPayload = Array.from(orderMap.values());

      if (ordersPayload.length) {
        const { error: ordersUpErr } = await supabase
          .from("orders")
          .upsert(ordersPayload, {
            onConflict: "retailer_id,pos_connection_id,external_order_id",
          });

        if (ordersUpErr) console.error("orders upsert error:", ordersUpErr);
        else console.log("orders headers published:", ordersPayload.length);
      } else {
        console.log("No orders to publish (headers).");
      }
    }
    // ----------- 4️⃣ Mark connection healthy -----------
    await supabase
      .from("pos_connections")
      .update({ last_synced_at: now, last_error: null, updated_at: now })
      .eq("id", connectionId);

    return new Response(JSON.stringify({ ok: true, imported: total }), {
      status: 200,
      headers: { ...cors, "Content-Type": "application/json" },
    });
  } catch (err: any) {
    console.error("pos-sync error:", err);
    return new Response(
      JSON.stringify({ error: err?.message ?? "Unknown error" }),
      { status: 500, headers: { ...cors, "Content-Type": "application/json" } },
    );
  }
});
/* To invoke locally:

  1. Run `supabase start` (see: https://supabase.com/docs/reference/cli/supabase-start)
  2. Make an HTTP request:

  curl -i --location --request POST 'http://127.0.0.1:54321/functions/v1/pos-sync' \
    --header 'Authorization: Bearer $SUPABASE_ANON_KEY' \
    --header 'Content-Type: application/json' \
    --data '{"name":"Functions"}'

*/
