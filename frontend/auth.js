import {
  InteractionRequiredAuthError,
  PublicClientApplication,
} from "@azure/msal-browser";


const config = window.APP_CONFIG;

if (!config) {
  throw new Error("config.js must be loaded before auth.js.");
}

const requiredSettings = [
  "ENTRA_TENANT_ID",
  "ENTRA_SPA_CLIENT_ID",
  "ENTRA_API_CLIENT_ID",
  "ENTRA_SCOPE",
];

for (const settingName of requiredSettings) {
  const value = String(config[settingName] || "").trim();
  if (!value || value.startsWith("REPLACE_WITH_")) {
    throw new Error(`Complete ${settingName} in frontend/config.js.`);
  }
}

const msalConfig = {
  auth: {
    clientId: config.ENTRA_SPA_CLIENT_ID,
    authority: `https://login.microsoftonline.com/${config.ENTRA_TENANT_ID}`,
    redirectUri: `${window.location.origin}/`,
    postLogoutRedirectUri: `${window.location.origin}/`,
    navigateToLoginRequestUrl: false,
  },
  cache: {
    cacheLocation: "sessionStorage",
    storeAuthStateInCookie: false,
  },
};

const tokenRequest = {
  scopes: [config.ENTRA_SCOPE],
};

export const msalApp = new PublicClientApplication(msalConfig);

let initializationPromise = null;


export async function initializeAuthentication() {
  if (!initializationPromise) {
    initializationPromise = (async () => {
      await msalApp.initialize();
      const redirectResponse = await msalApp.handleRedirectPromise();

      if (redirectResponse?.account) {
        msalApp.setActiveAccount(redirectResponse.account);
      }

      if (!msalApp.getActiveAccount()) {
        const [firstAccount] = msalApp.getAllAccounts();
        if (firstAccount) {
          msalApp.setActiveAccount(firstAccount);
        }
      }
    })();
  }

  return initializationPromise;
}


export async function signIn() {
  await initializeAuthentication();

  await msalApp.loginRedirect({
    scopes: ["openid", "profile", config.ENTRA_SCOPE],
    prompt: "select_account",
  });
}


export async function signOut() {
  await initializeAuthentication();

  await msalApp.logoutRedirect({
    account: msalApp.getActiveAccount() || undefined,
    postLogoutRedirectUri: `${window.location.origin}/`,
  });
}


export async function getAccessToken() {
  await initializeAuthentication();

  const account = msalApp.getActiveAccount();
  if (!account) {
    await signIn();
    throw new Error("Redirecting to Microsoft sign-in.");
  }

  try {
    const response = await msalApp.acquireTokenSilent({
      ...tokenRequest,
      account,
    });
    return response.accessToken;
  } catch (error) {
    if (error instanceof InteractionRequiredAuthError) {
      await msalApp.acquireTokenRedirect({
        ...tokenRequest,
        account,
      });
      throw new Error("Redirecting to renew the Microsoft session.");
    }

    throw error;
  }
}


export async function apiFetch(path, options = {}) {
  const accessToken = await getAccessToken();
  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${accessToken}`);

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return fetch(`${config.API_BASE_URL}${normalizedPath}`, {
    ...options,
    headers,
  });
}


export async function getCurrentUser() {
  const response = await apiFetch("/auth/me", {
    headers: { Accept: "application/json" },
  });

  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      body.detail || `Unable to load the signed-in user (${response.status}).`
    );
  }

  return body;
}


export async function requireSignedInUser() {
  await initializeAuthentication();

  if (!msalApp.getActiveAccount()) {
    await signIn();
    return null;
  }

  return getCurrentUser();
}
