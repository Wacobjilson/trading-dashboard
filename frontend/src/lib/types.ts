export interface Quote {
  symbol: string;
  name?: string;
  assetClass?: string;
  last: number;
  change: number;
  changePercent: number;
  weekChangePct: number;
  open: number;
  high: number;
  low: number;
  prevClose: number;
  volume: number;
  avgVolume?: number;
  relVolume?: number;
  atr?: number;
  trendStrength?: number;
  time: string;
}

export interface User {
  id: string;
  email: string;
  displayName: string;
  createdAt: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}
