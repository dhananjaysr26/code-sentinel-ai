with open("frontend/src/api/client.ts", "r") as f:
    content = f.read()

# Replace createReview method
old_create = """  createReview: async (request: CreateReviewRequest): Promise<Review> => {
    // Start the review in background mode
    const res = await fetch(`${BASE_URL}/reviews/?stream=true`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    
    if (!res.ok) {
        return handleResponse<Review>(res); // handles errors normally
    }
    
    const data = await res.json();
    const reviewId = data.id;

    // Listen to SSE until EOF, then fetch the completed review
    return new Promise((resolve, reject) => {
        const evtSource = new EventSource(`${BASE_URL}/reviews/${reviewId}/events/`);
        
        evtSource.onmessage = (event) => {
            try {
                const eventData = JSON.parse(event.data);
                
                if (eventData.type === "EOF") {
                    evtSource.close();
                    // Review is done in backend, now fetch the full record
                    reviewsApi.getReview(reviewId)
                        .then(resolve)
                        .catch(reject);
                } else {
                    // Dispatch event so UI components can optionally show live logs
                    window.dispatchEvent(new CustomEvent("ReviewLiveEvent", { detail: eventData }));
                    console.log(`[${eventData.reviewer}] ${eventData.event} -> ${eventData.details}`);
                }
            } catch (err) {
                console.error("SSE parse error", err);
            }
        };

        evtSource.onerror = (err) => {
            console.error("EventSource failed:", err);
            evtSource.close();
            // Try fetching anyway in case it finished and connection just dropped
            reviewsApi.getReview(reviewId)
                .then(resolve)
                .catch(reject);
        };
    });
  },"""

new_create = """  createReview: async (request: CreateReviewRequest): Promise<Review> => {
    // Start the review in background mode
    const res = await fetch(`${BASE_URL}/reviews/?stream=true`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    
    if (!res.ok) {
        return handleResponse<Review>(res);
    }
    
    return res.json() as Promise<Review>; // Resolves immediately!
  },

  listenToReviewEvents: (reviewId: string, onEvent: (eventData: any) => void) => {
    const evtSource = new EventSource(`${BASE_URL}/reviews/${reviewId}/events/`);
    evtSource.onmessage = (event) => {
        try {
            const eventData = JSON.parse(event.data);
            if (eventData.type === "EOF") {
                evtSource.close();
            } else {
                onEvent(eventData);
            }
        } catch (err) {
            console.error("SSE parse error", err);
        }
    };
    evtSource.onerror = (err) => {
        evtSource.close();
    };
    return () => evtSource.close();
  },"""

content = content.replace(old_create, new_create)
with open("frontend/src/api/client.ts", "w") as f:
    f.write(content)
