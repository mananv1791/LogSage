import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/api/runbooks")) {
          return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
        }
        if (url.includes("/api/incidents")) {
          return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
        }
        return Promise.resolve(new Response("{}", { status: 200 }));
      })
    );
  });

  it("renders the incident triage console", async () => {
    render(<App />);

    await waitFor(() => expect(screen.getByText("LogSage")).toBeInTheDocument());
    expect(screen.getByText("New incident")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Search logs, titles, incident types")).toBeInTheDocument();
  });
});
