import { Discovery } from "@/components/discovery";
import type { Metadata } from "next";

export const metadata: Metadata = {
  alternates: { canonical: "https://lordoftheskill.com" },
};

export default function Home() {
  return <Discovery />;
}
