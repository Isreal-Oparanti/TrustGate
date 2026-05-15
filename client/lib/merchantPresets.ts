import type { FormState } from "@/types";

export interface MerchantPreset {
  name: string;
  description: string;
  data: Partial<FormState>;
  documents: Record<string, { filename: string; state: "success" }>;
}

// Legit Merchant Preset (Tier 2: cac_certificate, utility_bill, directors_id)
const legitimateMerchant: MerchantPreset = {
  name: "Load Legit Merchant",
  description: "Realistic SME with medium volume",
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
    cac_certificate: { filename: "cac_certificate_sunshine.pdf", state: "success" },
    utility_bill: { filename: "utility_bill_lekki_2024.jpg", state: "success" },
    directors_id: { filename: "director_id_chioma_okonkwo.png", state: "success" },
  },
};

// Suspicious Merchant Preset (Tier 2: cac_certificate, utility_bill, directors_id)
const suspiciousMerchant: MerchantPreset = {
  name: "Load Suspicious Merchant",
  description: "Mismatched category with weak online presence",
  data: {
    business_name: "Global Import Services",
    tier: "tier2",
    rc_number: "RC 9876543",
    director_name: "Tunde Adeyemi",
    business_category: "logistics",
    website_url: "https://blogspot.com/globalimport",
    social_media_url: "https://facebook.com/profile.php?id=1234567",
    expected_monthly_volume: "₦8,500,000",
    bvn: "31265438917",
    nin: "19832756241",
    email: "tunde.biz99@gmail.com",
    phone: "+2347034567891",
    address: "Apartment 12B, Ikeja GRA, Lagos, Nigeria",
    bank_name: "Access Bank",
    bank_code: "044",
    account_number: "1098765432",
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

// High-Risk Merchant Preset (Tier 3: cac_certificate, utility_bill, directors_id, cac_form_cac2, cac_form_cac7, memart)
const highRiskMerchant: MerchantPreset = {
  name: "Load High-Risk Merchant",
  description: "Crypto/gambling styled with extreme volume expectations",
  data: {
    business_name: "FastCash Digital Network",
    tier: "tier3",
    rc_number: "RC 5555555",
    director_name: "Chukwudi Nwosu",
    business_category: "other",
    website_url: "https://fastcashdigital.xyz",
    social_media_url: "https://telegram.me/fastcash_updates",
    expected_monthly_volume: "₦45,000,000",
    bvn: "24789563214",
    nin: "18765432189",
    email: "admin@fastcashdigital.xyz",
    phone: "+2349067890123",
    address: "Plot 99, Victoria Island, Lagos, Nigeria",
    bank_name: "Other",
    bank_code: "000",
    account_number: "9999999999",
    account_name: "FastCash Digital Network",
    payment_security_question: "What is the first two digits of the payment code?",
    payment_security_answer: "24",
  },
  documents: {
    cac_certificate: { filename: "cac_fastcash_2024.pdf", state: "success" },
    utility_bill: { filename: "vi_electricity_invoice.jpg", state: "success" },
    directors_id: { filename: "directors_passport_chukwudi.png", state: "success" },
    cac_form_cac2: { filename: "cac_form_cac2_fastcash.pdf", state: "success" },
    cac_form_cac7: { filename: "cac_form_cac7_fastcash.pdf", state: "success" },
    memart: { filename: "memart_registration_fastcash.pdf", state: "success" },
  },
};

export const merchantPresets: MerchantPreset[] = [
  legitimateMerchant,
  suspiciousMerchant,
  highRiskMerchant,
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
