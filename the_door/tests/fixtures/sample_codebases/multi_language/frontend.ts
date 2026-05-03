/**
 * Frontend API client.
 */
export async function fetchHealth(): Promise<{ status: string }> {
    const response = await fetch('/health');
    return response.json();
}
