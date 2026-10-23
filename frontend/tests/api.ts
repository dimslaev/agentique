import { LoginService, OpenAPI } from "../src/shared/api"

OpenAPI.BASE = `${process.env.VITE_API_URL}`

export const createUser = async ({ email }: { email: string }) => {
  return await LoginService.requestSignInLink({ requestBody: { email } })
}
