// src/supabaseClient.js
import { createClient } from "@supabase/supabase-js";

export const publicDemo = import.meta.env.VITE_PUBLIC_DEMO === "true";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || "https://example.invalid";
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || "public-demo-no-backend";

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
