import {
  ArrowRight, ArrowDown, Eye, EyeOff, Ban, Banknote, Repeat, TrendingDown,
  Plug, Brain, Zap, ChartColumn, RefreshCw, Handshake, Camera, Check, X,
  CircleCheck, TriangleAlert, MapPin, Package, ShoppingCart, Car, Tag, CircleHelp,
} from "lucide-react";

const icons = {
  arrowRight: ArrowRight, arrowDown: ArrowDown, eye: Eye, eyeOff: EyeOff,
  ban: Ban, banknote: Banknote, repeat: Repeat, trendingDown: TrendingDown,
  plug: Plug, brain: Brain, zap: Zap, chart: ChartColumn, refresh: RefreshCw,
  handshake: Handshake, camera: Camera, check: Check, close: X,
  success: CircleCheck, warning: TriangleAlert, mapPin: MapPin,
  package: Package, cart: ShoppingCart, car: Car, tag: Tag,
};

export default function Icon({ name, size = 20, label, className = "", ...props }) {
  const Component = icons[name] || CircleHelp;
  return <Component size={size} strokeWidth={1.8} className={`app-icon ${className}`} aria-hidden={label ? undefined : true} aria-label={label} role={label ? "img" : undefined} focusable="false" {...props} />;
}
