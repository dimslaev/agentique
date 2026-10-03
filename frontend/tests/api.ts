import { OpenAPI, UsersService } from "../src/client"

OpenAPI.BASE = `${process.env.VITE_API_URL}`

export const createUser = async ({
  email,
  password,
}: {
  email: string
  password: string
}) => {
  return await UsersService.registerUser({
    requestBody: {
      email,
      password,
      full_name: "Test User",
    },
  })
}
