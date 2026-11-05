// REST API of the service. Paths are relative: the app can live under a
// path prefix behind the data space connector (e.g. /container-location/).

async function request(path, options = {}) {
    let response;
    try {
        response = await fetch(path, {
            headers: { "Content-Type": "application/json" },
            ...options,
        });
    } catch (error) {
        throw new Error("The server cannot be reached");
    }
    let body = null;
    try {
        body = await response.json();
    } catch (error) {
        // empty or non-JSON body
    }
    if (!response.ok) {
        throw new Error((body && body.error) || `${response.status} ${response.statusText}`);
    }
    return body;
}

export const api = {
    status: () => request("api/status"),
    layout: (serviceLevel) => request(`api/layout?service_level=${encodeURIComponent(serviceLevel)}`),
    jobs: () => request("api/jobs"),
    job: (id) => request(`api/jobs/${encodeURIComponent(id)}`),
    createJob: (params) => request("api/jobs", { method: "POST", body: JSON.stringify(params) }),
    cancelJob: (id) => request(`api/jobs/${encodeURIComponent(id)}`, { method: "DELETE" }),
};
