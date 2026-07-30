// Public application identifiers. These are not client secrets.
const ENTRA_API_CLIENT_ID = "b76c458e-a999-495f-b9ff-970eb38c5996";

window.APP_CONFIG = Object.freeze({
  API_BASE_URL: "http://localhost:8000/api/v1",
  ENTRA_TENANT_ID: "4e691540-9ece-4257-9dc4-48840f9646ab",
  ENTRA_SPA_CLIENT_ID: "ec967c96-fa63-43c4-a668-401a2bdabc0b",
  ENTRA_API_CLIENT_ID,
  ENTRA_SCOPE: `api://${ENTRA_API_CLIENT_ID}/access_as_user`,
});

