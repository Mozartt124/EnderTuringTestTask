import {
  type QueryClient,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { redirect, useNavigate } from "@tanstack/react-router"

import {
  type Body_login_login_access_token as AccessToken,
  LoginService,
  type Permission,
  type UserMe,
  type UserRegister,
  UsersService,
} from "@/client"
import { handleError } from "@/utils"
import useCustomToast from "./useCustomToast"

const isLoggedIn = () => {
  return localStorage.getItem("access_token") !== null
}

const currentUserQueryOptions = {
  queryKey: ["currentUser"],
  queryFn: async () => (await UsersService.readUserMe()).data,
}

// Permissions come from the backend (/users/me); the UI only mirrors them.
const hasPermission = (
  user: UserMe | null | undefined,
  permission: Permission,
): boolean => user?.permissions.includes(permission) ?? false

// Route guard: always refetches /users/me so a role change made during the
// current session is honored on the next navigation.
const requirePermission = async (
  queryClient: QueryClient,
  permission: Permission,
) => {
  const user = await queryClient.fetchQuery({
    ...currentUserQueryOptions,
    staleTime: 0,
  })
  if (!hasPermission(user, permission)) {
    throw redirect({ to: "/" })
  }
}

const useAuth = () => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const { data: user } = useQuery<UserMe | null, Error>({
    ...currentUserQueryOptions,
    enabled: isLoggedIn(),
  })

  const signUpMutation = useMutation({
    mutationFn: (data: UserRegister) =>
      UsersService.registerUser({ body: data }),
    onSuccess: () => {
      navigate({ to: "/login" })
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] })
    },
  })

  const login = async (data: AccessToken) => {
    const response = await LoginService.loginAccessToken({
      body: data,
    })
    localStorage.setItem("access_token", response.data.access_token)
  }

  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: () => {
      navigate({ to: "/" })
    },
    onError: handleError.bind(showErrorToast),
  })

  const logout = () => {
    localStorage.removeItem("access_token")
    // Drop cached data (including permissions) so the next user starts clean.
    queryClient.clear()
    navigate({ to: "/login" })
  }

  return {
    signUpMutation,
    loginMutation,
    logout,
    user,
  }
}

export { hasPermission, isLoggedIn, requirePermission }
export default useAuth
