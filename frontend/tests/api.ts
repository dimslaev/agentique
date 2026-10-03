import { OpenAPI, UsersService } from "../src/client"

OpenAPI.BASE = `${process.env.VITE_API_URL}`

export const createUser = async ({ email }: { email: string }) => {
  return await UsersService.registerUser({ requestBody: { email } })
}
