import type { FormState } from "@/types";

export interface MerchantPreset {
  name: string;
  description: string;
  data: Partial<FormState>;
  documents: Record<string, { filename: string; state: "success"; sourcePath?: string }>;
}

const legitimateMerchant: MerchantPreset = {
  name: "Load Legit Merchant",
  description: "Hubmart profile with strong public business signals",
  data: {
    business_name: "Hubmart Stores Limited",
    tier: "tier2",
    rc_number: "RC 1119111",
    director_name: "Benedict Omonua",
    business_category: "retail",
    website_url: "https://hubmart.com",
    social_media_url: "https://ng.linkedin.com/company/hubmart-stores",
    expected_monthly_volume: "₦65,000,000",
    bvn: "22182441379",
    nin: "22118456789",
    email: "info@hubmart.com",
    phone: "2348028244137",
    address: "35 Adeola Odeku Street, Victoria Island, Lagos, Nigeria",
    bank_name: "GTBank",
    bank_code: "058",
    account_number: "0123456789",
    account_name: "Hubmart Stores Limited",
    payment_security_question: "What is the first two digits of the payment code?",
    payment_security_answer: "24",
  },
  documents: {
    cac_certificate: { filename: "hubmart_stores_cac.png", state: "success" },
    utility_bill: { filename: "hubmart_adeola_odeku_utility.png", state: "success" },
    directors_id: { filename: "hubmart_director_id.png", state: "success" },
  },
};

const fraudMerchant: MerchantPreset = {
  name: "Load Fraud Merchant",
  description: "High-risk merchant with weak identity and behaviour signals",
  data: {
    business_name: "Sunshine Electronics Ltd",
    tier: "tier2",
    rc_number: "RC 1234567",
    director_name: "Tunde Adeyemi",
    business_category: "retail",
    website_url: "https://sunshine-electronics-payments.xyz",
    social_media_url: "https://facebook.com/profile.php?id=1234567",
    expected_monthly_volume: "₦45,000,000",
    bvn: "31289563214",
    nin: "19832756241",
    email: "sunshineelectronics.demo@gmail.com",
    phone: "2349067890123",
    address: "Apartment 12B, Ikeja GRA, Lagos, Nigeria",
    bank_name: "GTBank",
    bank_code: "058",
    account_number: "0123456789",
    account_name: "Tunde Adeyemi",
    payment_security_question: "What is the first two digits of the payment code?",
    payment_security_answer: "24",
  },
  documents: {
    cac_certificate: { filename: "cac_reg_2022.pdf", state: "success" },
    utility_bill: { filename: "power_bill_ikeja.jpg", state: "success" },
    directors_id: { filename: "national_id_tunde.png", state: "success" },
  },
};

export const merchantPresets: MerchantPreset[] = [
  legitimateMerchant,
  fraudMerchant,
];

export const presetOptions = [
  { label: "Select preset merchant...", value: "" },
  ...merchantPresets.map((preset) => ({
    label: preset.name,
    value: preset.name,
    description: preset.description,
  })),
];

export function getMerchantPreset(name: string): MerchantPreset | undefined {
  return merchantPresets.find((p) => p.name === name);
}
