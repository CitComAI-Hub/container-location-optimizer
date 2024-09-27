export class HttpClient {
    #serverURL = "http://127.0.0.1:5000/";
    #networkTimeOut = 7000; // 7s to abort

    async get(path, params) {

        // Build URL
        const url = new URL(this.#serverURL);
        url.pathname = path;

        const searchParams = new URLSearchParams(params);

        try {
            // Create abort controller to handle timeout
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), this.#networkTimeOut);

            // Fetch with timeout
            const response = await fetch(url.toString() + '?' + searchParams.toString(), { signal: controller.signal });
            clearTimeout(timeoutId);

            if (response.status >= 200 && response.status <= 299) {
                const jsonResponse = await response.json();
                return jsonResponse;
            } else {
                // Handle errors
                console.error(response.status, response.statusText);
                return { error: response.statusText }
            }
        } catch (error) {
            // Timeout error
            return { error: "Request timeout" }
        }
    }
}