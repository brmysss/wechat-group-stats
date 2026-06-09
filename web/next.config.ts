import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "wx.qlogo.cn" },
      { protocol: "https", hostname: "mmhead.c2c.wechat.com" },
    ],
  },
};

export default nextConfig;
