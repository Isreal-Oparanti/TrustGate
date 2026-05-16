import type { FormState } from "@/types";

export interface MerchantPreset {
  name: string;
  description: string;
  data: Partial<FormState>;
  documents: Record<string, { filename: string; state: "success"; sourcePath?: string }>;
}

const legitimateMerchant: MerchantPreset = {
  name: "Load Legit Merchant",
  description: "Legitimate SME with original uploaded documents",
  data: {
    business_name: "Sunshine Electronics Ltd",
    tier: "tier2",
    rc_number: "RC 1234567",
    director_name: "Chioma Okonkwo",
    business_category: "retail",
    website_url: "https://sunshineelectronics.com.ng",
    social_media_url: "https://instagram.com/sunshineelectronics_ng",
    expected_monthly_volume: "₦2,500,000",
    bvn: "22147856329",
    nin: "22118456789",
    email: "chioma@sunshineelectronics.com.ng",
    phone: "2348034567890",
    address: "No. 45, Lekki Phase 1, Lagos, Nigeria",
    bank_name: "GTBank",
    bank_code: "058",
    account_number: "0123456789",
    account_name: "Sunshine Electronics Ltd",
    payment_security_question: "What is the first two digits of the payment code?",
    payment_security_answer: "24",
  },
  documents: {
    cac_certificate: {
      filename: "sunshine_cac_certificate.png",
      state: "success",
      sourcePath: "/uploads/83207002-d5a3-48f5-a01c-79a627ea9904/cd9f5dd0-8d95-4c7c-aaef-3ce8c54613cc_CAC.png",
    },
    utility_bill: {
      filename: "sunshine_utility_bill.png",
      state: "success",
      sourcePath: "/uploads/83207002-d5a3-48f5-a01c-79a627ea9904/c465376f-9ebd-43c3-ac8a-f657fc3510a8_UTILITY.png",
    },
    directors_id: {
      filename: "sunshine_director_id.png",
      state: "success",
      sourcePath: "/uploads/83207002-d5a3-48f5-a01c-79a627ea9904/3ce1a105-b5c5-4981-acf5-79a523a51491_iD.png",
    },
  },
};

const fraudMerchant: MerchantPreset = {
  name: "Load Fraud Merchant",
  description: "High-risk merchant with weak identity and behaviour signals",
  data: {
    business_name: "FastCash Digital Network",
    tier: "tier2",
    rc_number: "RC 5555555",
    director_name: "Chukwudi Nwosu",
    business_category: "other",
    website_url: "https://fastcashdigital.xyz",
    social_media_url: "https://telegram.me/fastcash_updates",
    expected_monthly_volume: "₦45,000,000",
    bvn: "31289563214",
    nin: "19832756241",
    email: "admin@fastcashdigital.xyz",
    phone: "2349067890123",
    address: "Apartment 12B, Ikeja GRA, Lagos, Nigeria",
    bank_name: "GTBank",
    bank_code: "058",
    account_number: "0123456789",
    account_name: "FastCash Digital Network",
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
