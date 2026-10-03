import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { LoginService, type UserPublic, UsersService } from "@/client"

const REDIRECT_KEY = "after_sign_in"

const isLoggedIn = () => {
  return localStorage.getItem("access_token") !== null
}

const signInWithLink = async (token: string) => {
  const response = await LoginService.loginWithLink({
    requestBody: { token },
  })
  localStorage.setItem("access_token", response.access_token)
}

// The sign-in link opens in a new tab from the email, so the page a reader was
// on when asked to sign in has to outlive this one.
const rememberRedirect = (path: string | undefined) => {
  if (path) localStorage.setItem(REDIRECT_KEY, path)
  else localStorage.removeItem(REDIRECT_KEY)
}

const takeRedirect = () => {
  const path = localStorage.getItem(REDIRECT_KEY)
  localStorage.removeItem(REDIRECT_KEY)
  // Only a path on this site, never an absolute URL.
  return path?.startsWith("/") && !path.startsWith("//") ? path : null
}

const useAuth = () => {
  const navigate = useNavigate()

  const { data: user } = useQuery<UserPublic | null, Error>({
    queryKey: ["currentUser"],
    queryFn: UsersService.readUserMe,
    enabled: isLoggedIn(),
  })

  const logout = () => {
    localStorage.removeItem("access_token")
    navigate({ to: "/login" })
  }

  return {
    logout,
    user,
  }
}

export { isLoggedIn, rememberRedirect, signInWithLink, takeRedirect }
export default useAuth
