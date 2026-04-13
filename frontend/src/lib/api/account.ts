import { get, post, request } from "@/lib/api/client";
import type {
  AccountDeleteRequest,
  AccountDeleteResponse,
  AccountProfile,
  AccountProfileUpdateRequest,
  SignUpValidationRequest,
  SignUpValidationResponse,
  UsernameAvailabilityResponse,
} from "@/lib/api";

export const accountApi = {
  getMyAccountProfile: () => get<AccountProfile>("/api/account/me"),
  updateMyAccountProfile: (payload: AccountProfileUpdateRequest) =>
    request<AccountProfile>("/api/account/me", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  deleteMyAccount: (payload: AccountDeleteRequest) =>
    request<AccountDeleteResponse>("/api/account/me", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  validateSignup: (payload: SignUpValidationRequest) =>
    post<SignUpValidationResponse>("/api/account/signup/validate", payload),
  checkUsernameAvailability: (username: string) =>
    get<UsernameAvailabilityResponse>(`/api/account/username-availability?username=${encodeURIComponent(username)}`),
};
