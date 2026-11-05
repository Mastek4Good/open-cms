// Tailwind theme extension. Loaded before the vendored Tailwind build so the
// brand palette is available when it compiles the page's classes.
//
// Lives in its own file rather than an inline <script> so that the Content
// Security Policy can pin script-src to this origin. See app/security/headers.py.
window.tailwind = window.tailwind || {};
window.tailwind.config = {
    theme: {
        extend: {
            colors: {
                brand: {
                    50: '#f0f9ff',
                    100: '#e0f2fe',
                    500: '#0ea5e9',
                    600: '#0369a1',
                    700: '#075985',
                    800: '#0c4a6e',
                    900: '#1e3a5f',
                }
            }
        }
    }
};
