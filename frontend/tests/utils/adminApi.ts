// Test helpers that act as the first Admin through the regular API.
import { LoginService, type UserRole, UsersService } from "../../src/client"
import { client } from "../../src/client/client.gen"
import { firstSuperuser, firstSuperuserPassword } from "../config.ts"

client.setConfig({
  baseURL: `${process.env.VITE_API_URL}`,
})

const adminHeaders = async () => {
  const { data } = await LoginService.loginAccessToken({
    body: { username: firstSuperuser, password: firstSuperuserPassword },
  })
  return { Authorization: `Bearer ${data.access_token}` }
}

export const createUserWithRole = async ({
  email,
  password,
  role,
}: {
  email: string
  password: string
  role: UserRole
}) => {
  const response = await UsersService.createUser({
    body: { email, password, role, is_active: true },
    headers: await adminHeaders(),
  })
  return response.data
}

export const getUser = async (userId: string) => {
  const response = await UsersService.readUserById({
    path: { user_id: userId },
    headers: await adminHeaders(),
  })
  return response.data
}

export const setUserRole = async (userId: string, role: UserRole) => {
  await UsersService.updateUser({
    path: { user_id: userId },
    body: { role },
    headers: await adminHeaders(),
  })
}
