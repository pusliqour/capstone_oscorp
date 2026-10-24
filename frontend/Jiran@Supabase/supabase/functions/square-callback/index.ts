// Follow this setup guide to integrate the Deno language server with your editor:
// https://deno.land/manual/getting_started/setup_your_environment
// This enables autocomplete, go to definition, etc.

// Setup type definitions for built-in Supabase Runtime APIs
// import { serve } from "https://deno.land/std/http/server.ts";
// import { createClient } from "https://esm.sh/@supabase/supabase-js";

// serve(async (req) => {

//   const url = new URL(req.url);
//   const consumerId = url.searchParams.get("consumer_id");

//   if (!consumerId) {
//     return new Response("Missing consumer_id", { status: 400 });
//   }

//   const supabase = createClient(
//     Deno.env.get("SUPABASE_URL")!,
//     Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
//   );

//   // 🔎 1️⃣ Find the pos_connection
//   const { data: connection, error: connectionError } = await supabase
//     .from("pos_connections")
//     .select("id")
//     .eq("consumer_id", consumerId)
//     .single();

//   if (connectionError || !connection) {
//     return new Response("POS connection not found", { status: 404 });
//   }

//   const posConnectionId = connection.id;

//   // 🔄 2️⃣ Fetch Items (Handle Pagination)
//   let nextUrl: string | null = "https://unify.apideck.com/pos/inventory";

//   while (nextUrl) {

//     const inventoryResponse = await fetch(nextUrl, {
//       headers: {
//         "x-apideck-app-id": Deno.env.get("APIDECK_APP_ID")!,
//         "x-apideck-consumer-id": consumerId,
//         "Authorization": `Bearer ${Deno.env.get("APIDECK_API_KEY")}`
//       }
//     });

//     const inventoryData = await inventoryResponse.json();

//     for (const item of inventoryData.data) {

//       for (const variation of item.variations || []) {

//         await supabase.from("pos_items").upsert({
//           id: variation.id, // variation is the sellable entity
//           pos_connection_id: posConnectionId,
//           name: item.name,
//           sku: variation.id,
//           category: item.product_type,
//           price: variation.price_amount / 100, // convert minor units
//           currency: variation.price_currency,
//           quantity: null, // inventory endpoint separate
//           is_active: !variation.deleted,
//           updated_at: new Date().toISOString()
//         });
//       }
//     }

//     nextUrl = inventoryData.links?.next ?? null;
//   }

//   return new Response("Inventory Synced Successfully");
// });
// ----------------------------------------------------------------------------------------------
// Deno + Supabase Edge Function: Square callback -> update DB -> redirect to /inventory
import { serve } from "https://deno.land/std/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const FRONTEND_URL = Deno.env.get("FRONTEND_URL")!;

const APIDECK_APP_ID = Deno.env.get("APIDECK_APP_ID")!;
const APIDECK_API_KEY = Deno.env.get("APIDECK_API_KEY")!;

function html(body: string, status = 200) {
  return new Response(`<!doctype html><html><body>${body}</body></html>`, {
    status,
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

serve(async (req) => {
  try {
    const url = new URL(req.url);
    const consumerId = url.searchParams.get("consumer_id");

    if (!consumerId) {
      return html("<h3>Missing consumer_id</h3>", 400);
    }

    const supabase = createClient(SUPABASE_URL, SERVICE_ROLE_KEY);

    // --------------------------------------------
    // 1) Get connections from Apideck
    // --------------------------------------------
    const vaultRes = await fetch(
      "https://unify.apideck.com/vault/connections",
      {
        method: "GET",
        headers: {
          "x-apideck-app-id": APIDECK_APP_ID,
          "x-apideck-consumer-id": consumerId,
          Authorization: `Bearer ${APIDECK_API_KEY}`,
        },
      },
    );

    const vaultJson = await vaultRes.json();

    if (!vaultRes.ok) {
      console.error("Apideck error:", vaultJson);
      return html("<h3>Failed to retrieve connections from Apideck</h3>", 502);
    }

    const squareConnection = (vaultJson?.data ?? []).find(
      (c: any) =>
        c?.service_id === "square" &&
        (c?.state === "callable" || c?.state === "authorized"),
    );

    if (!squareConnection) {
      return html("<h3>Square connection not authorized yet</h3>", 404);
    }

    // --------------------------------------------
    // 2) Update DB record to connected
    // --------------------------------------------
    const { data: updatedConn, error: upErr } = await supabase
      .from("pos_connections")
      .update({
        status: "connected",
        vault_connection_id: squareConnection.id,
        metadata: squareConnection,
        last_error: null,
        updated_at: new Date().toISOString(),
      })
      .eq("consumer_id", consumerId)
      .eq("provider", "square")
      .select("id")
      .single();

    if (upErr || !updatedConn) {
      console.error("DB update error:", upErr);
      return html("<h3>Failed to update connection in database</h3>", 500);
    }

    const squareConnectionId = updatedConn.id;

    // --------------------------------------------
    // 3) ACTIVATE SQUARE (call pos-switch-provider)
    // --------------------------------------------
    await fetch(`${SUPABASE_URL}/functions/v1/pos-switch-provider`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${SERVICE_ROLE_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        retailer_id: consumerId,
        target_provider: "square",
        connection_id: squareConnectionId,
      }),
    });

    // --------------------------------------------
    // 4) Trigger fresh POS sync (optional but ideal)
    // --------------------------------------------
    // fetch(`${SUPABASE_URL}/functions/v1/pos-sync`, {
    //   method: "POST",
    //   headers: {
    //     Authorization: `Bearer ${SERVICE_ROLE_KEY}`,
    //     "Content-Type": "application/json",
    //   },
    //   body: JSON.stringify({
    //     retailer_id: consumerId,
    //   }),
    // }).catch((err) => {
    //   console.error("Background pos-sync failed:", err);
    // });

    // --------------------------------------------
    // 5) Redirect back to frontend
    // --------------------------------------------
    return Response.redirect(`${FRONTEND_URL}/loading`, 302);
  } catch (err) {
    console.error("square-callback error:", err);
    return html("<h3>Unexpected error in Square callback</h3>", 500);
  }
});
/* To invoke locally:

  1. Run `supabase start` (see: https://supabase.com/docs/reference/cli/supabase-start)
  2. Make an HTTP request:

  curl -i --location --request POST 'http://127.0.0.1:54321/functions/v1/square-callback' \
    --header 'Authorization: Bearer $SUPABASE_ANON_KEY' \
    --header 'Content-Type: application/json' \
    --data '{"name":"Functions"}'

*/
