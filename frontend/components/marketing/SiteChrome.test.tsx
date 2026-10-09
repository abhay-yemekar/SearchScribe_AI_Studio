import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import { renderToString } from "react-dom/server";
import SiteChrome from "./SiteChrome";
import { RewriteShowcase, StudioStory } from "./StudioScenes";

const session = vi.hoisted(() => ({ user: null as null | { name: string } }));
vi.mock("@/features/auth/useSession", () => ({ useSession: () => session }));

beforeEach(() => {
  session.user = null;
  localStorage.clear();
  vi.stubGlobal("matchMedia", () => ({ matches: true }));
});

test("stored theme survives a public page remount and can be changed back", () => {
  localStorage.setItem("searchscribe.public-theme", "dark");
  const first = render(<SiteChrome>Home</SiteChrome>);
  expect(screen.getByRole("button", { name: "Use light theme" })).toBeInTheDocument();
  first.unmount();
  render(<SiteChrome>Features</SiteChrome>);
  fireEvent.click(screen.getByRole("button", { name: "Use light theme" }));
  expect(localStorage.getItem("searchscribe.public-theme")).toBe("light");
  expect(screen.getByRole("button", { name: "Use dark theme" })).toBeInTheDocument();
});

test("signed-in header gives account and workspace distinct destinations", () => {
  session.user = { name: "Writer" };
  const { container } = render(<SiteChrome>Home</SiteChrome>);
  const header = within(container.querySelector("header")!);
  expect(header.getByRole("link", { name: "Account" })).toHaveAttribute(
    "href",
    "/account",
  );
  expect(header.getByRole("link", { name: "Open workspace" })).toHaveAttribute(
    "href",
    "/dashboard",
  );
  expect(header.queryByRole("link", { name: "Workspace" })).toBeNull();
});

test("theme toggle works when browser storage cannot be written", () => {
  const blocked = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new DOMException("Storage blocked", "SecurityError");
  });
  const first = render(<SiteChrome>Home</SiteChrome>);
  fireEvent.click(screen.getByRole("button", { name: "Use dark theme" }));
  first.unmount();
  render(<SiteChrome>Features</SiteChrome>);
  fireEvent.click(screen.getByRole("button", { name: "Use light theme" }));
  expect(screen.getByRole("button", { name: "Use dark theme" })).toBeInTheDocument();
  blocked.mockRestore();
});

test("public controls wait for hydration and respond to their first enabled click", () => {
  const content = (
    <SiteChrome>
      <StudioStory />
      <RewriteShowcase />
    </SiteChrome>
  );
  const server = document.createElement("div");
  server.innerHTML = renderToString(content);
  document.body.append(server);
  try {
    const initial = within(server);
    expect(initial.getByRole("button", { name: "Open navigation" })).toBeDisabled();
    expect(initial.getByRole("button", { name: "Use dark theme" })).toBeDisabled();
    expect(initial.getByRole("button", { name: /04\s*SEO/ })).toBeDisabled();
    expect(initial.getByRole("tab", { name: "Casual" })).toBeDisabled();
    expect(initial.getAllByRole("link", { name: "Start writing" })[0]).toHaveAttribute(
      "href",
      "/login?mode=signup",
    );
  } finally {
    server.remove();
  }

  render(content);
  const menu = screen.getByRole("button", { name: "Open navigation" });
  expect(menu).toBeEnabled();
  fireEvent.click(menu);
  expect(screen.getByRole("navigation", { name: "Mobile navigation" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: /04\s*SEO/ }));
  expect(screen.getByText("A first look at Kerala")).toBeVisible();
  fireEvent.click(screen.getByRole("tab", { name: "Casual" }));
  expect(screen.getByRole("tabpanel")).toHaveTextContent("slowing down");
});
