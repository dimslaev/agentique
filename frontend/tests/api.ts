import { LoginService, OpenAPI } from "../src/client"

OpenAPI.BASE = `${process.env.VITE_API_URL}`

export const createUser = async ({ email }: { email: string }) => {
  return await LoginService.requestSignInLink({ requestBody: { email } })
}
