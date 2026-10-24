// Follow this setup guide to integrate the Deno language server with your editor:
// https://deno.land/manual/getting_started/setup_your_environment
// This enables autocomplete, go to definition, etc.

// Setup type definitions for built-in Supabase Runtime APIs


// 🔑 CORS headers allow your local frontend to talk to the Supabase cloud
//-------------------------------------------------------------------------------------------------
// import { serve } from "https://deno.land/std/http/server.ts";
// import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// const corsHeaders = {
//   "Access-Control-Allow-Origin": "*",
//   "Access-Control-Allow-Headers":
//     "authorization, x-client-info, apikey, content-type",
// };

// serve(async (req) => {
//   if (req.method === "OPTIONS") {
//     return new Response("ok", { headers: corsHeaders });
//   }

//   try {
//     console.log("---- CONNECT SQUARE FUNCTION START ----");
//     console.log("All headers:", Object.fromEntries(req.headers.entries()));
//     const authHeader = req.headers.get("Authorization");
//     console.log("Authorization header present:", !!authHeader);

//     if (!authHeader) {
//       console.log("❌ No Authorization header received");
//       return new Response(
//         JSON.stringify({ error: "No authorization header" }),
//         {
//           status: 401,
//           headers: { ...corsHeaders, "Content-Type": "application/json" },
//         }
//       );
//     }

//     const token = authHeader.replace("Bearer ", "");
//     console.log("Token preview:", token.substring(0, 20) + "...");

//     const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
//     const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;


//     console.log("SUPABASE_URL exists:", !!supabaseUrl);
//     console.log("SERVICE_ROLE_KEY exists:", !!serviceRoleKey);
//     const supabase = createClient(supabaseUrl, serviceRoleKey);

//     const {
//       data: { user },
//       error: userError,
//     } = await supabase.auth.getUser(token);

//     console.log("User from JWT:", user);
//     console.log("User error:", userError);

//     if (userError || !user) {
//       return new Response(
//         JSON.stringify({ error: "Invalid session", details: userError }),
//         {
//           status: 401,
//           headers: { ...corsHeaders, "Content-Type": "application/json" },
//         }
//       );
//     }

//     const retailerId = user.id;
//     console.log("Retailer ID:", retailerId);


//     // 2️⃣ Create Apideck Vault session
//     console.log("Creating Apideck Vault session...");

//     const apideckResponse = await fetch(
//       "https://unify.apideck.com/vault/sessions",
//       {
//         method: "POST",
//         headers: {
//           "x-apideck-app-id": Deno.env.get("APIDECK_APP_ID")!,
//           Authorization: `Bearer ${Deno.env.get("APIDECK_API_KEY")}`,
//           "x-apideck-consumer-id": retailerId,
//           "Content-Type": "application/json",
//         },
//         body: JSON.stringify({
//           redirect_uri: `${supabaseUrl}/functions/v1/square-callback`,
//           settings: {
//             unified_apis: ["pos"],
//           },
//         }),
//       }
//     );

//     console.log("Apideck response status:", apideckResponse.status);

//     const apideckJson = await apideckResponse.json();
//     console.log("Apideck response body:", apideckJson);

//     if (!apideckResponse.ok) {
//       console.log("❌ Apideck Vault session creation failed");
//       return new Response(
//         JSON.stringify({ error: "Apideck error", details: apideckJson }),
//         {
//           status: apideckResponse.status, headers: { ...corsHeaders, "Content-Type": "application/json" },
//         }
//       );
//     }

//     const vaultUrl =
//       apideckJson?.data?.session_uri ||
//       apideckJson?.data?.url ||
//       apideckJson?.url;

//     if (!vaultUrl) {
//       return new Response(
//         JSON.stringify({ error: "No vault URL returned", details: apideckJson }),
//         { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
//       );
//     }

//     console.log("✅ Vault URL generated:", vaultUrl);

//     console.log("---- CONNECT SQUARE FUNCTION SUCCESS ----");

//     return new Response(JSON.stringify({ vault_url: vaultUrl }), {
//       status: 200,
//       headers: { ...corsHeaders, "Content-Type": "application/json" },
//     });
//   } catch (err: any) {
//     console.log("💥 Unexpected error:", err);

//     return new Response(JSON.stringify({ error: err.message }), {
//       status: 500,
//       headers: { ...corsHeaders, "Content-Type": "application/json" },
//     });
//   }
// });
//-------------------------------------------------------------------------------------------------

import { serve } from "https://deno.land/std/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const authHeader = req.headers.get("Authorization");
    if (!authHeader) {
      return new Response(
        JSON.stringify({ error: "No authorization header" }),
        { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const token = authHeader.replace("Bearer ", "");

    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    // Validate user
    const {
      data: { user },
      error: userError,
    } = await supabase.auth.getUser(token);

    if (userError || !user) {
      return new Response(
        JSON.stringify({ error: "Invalid session" }),
        { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const retailerId = user.id;

    // Create Vault session
    const apideckResponse = await fetch(
      "https://unify.apideck.com/vault/sessions",
      {
        method: "POST",
        headers: {
          "x-apideck-app-id": Deno.env.get("APIDECK_APP_ID")!,
          Authorization: `Bearer ${Deno.env.get("APIDECK_API_KEY")}`,
          "x-apideck-consumer-id": retailerId,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          redirect_uri: `${Deno.env.get("SUPABASE_URL")}/functions/v1/square-callback?consumer_id=${retailerId}`,
          settings: {
            unified_apis: ["pos"],
            auto_redirect: true,     // ✅ ensure Vault sends users back
            isolation_mode: true     // optional: hide “integrations overview” link
          }
        }),
      }
    );

    const apideckJson = await apideckResponse.json();

    if (!apideckResponse.ok) {
      return new Response(
        JSON.stringify({ error: "Apideck error", details: apideckJson }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const vaultUrl =
      apideckJson?.data?.session_uri ||
      apideckJson?.data?.url ||
      apideckJson?.url;

    const vaultSessionId = apideckJson?.data?.id || null;

    if (!vaultUrl) {
      return new Response(
        JSON.stringify({ error: "No vault URL returned" }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Upsert connection record
    const { error: dbError } = await supabase
      .from("pos_connections")
      .upsert(
        {
          retailer_id: retailerId,
          provider: "square",
          consumer_id: retailerId,
          vault_session_id: vaultSessionId,
          status: "pending",
          is_active: true,
          metadata: apideckJson, // DO NOT stringify
        },
        { onConflict: "retailer_id,provider" }
      );

    if (dbError) {
      return new Response(
        JSON.stringify({ error: "Database error", details: dbError }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    return new Response(
      JSON.stringify({ vault_url: vaultUrl }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (err: any) {
    return new Response(
      JSON.stringify({ error: err.message }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
/* To invoke locally:

  1. Run `supabase start` (see: https://supabase.com/docs/reference/cli/supabase-start)
  2. Make an HTTP request:

  curl -i --location --request POST 'http://127.0.0.1:54321/functions/v1/connect-square' \
    --header 'Authorization: Bearer $SUPABASE_ANON_KEY' \
    --header 'Content-Type: application/json' \
    --data '{"name":"Functions"}'

*/
