import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import type { ArticleDetail } from "@/lib/api/schemas";
import DashboardPage from "./page";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  save: vi.fn(),
  remove: vi.fn(),
  generate: vi.fn(),
  logout: vi.fn(),
}));
const original: ArticleDetail = {
  id: 1,
  title: "Original title",
  query: "Original topic",
  status: "complete",
  current_version: 1,
  content: {
    title: "Original title",
    introduction: "Original introduction",
    sections: [
      {
        id: "section01",
        heading: "First section",
        paragraphs: ["First paragraph"],
        bullets: [],
      },
    ],
    conclusion: "Original conclusion",
  },
  seo: {
    title: "SEO title",
    description: "SEO description.",
    keywords: ["article"],
    og_title: null,
    og_description: null,
    canonical_url: null,
    robots: "index, follow",
  },
  markdown: "# Original title",
  html: "<h1>Original title</h1>",
  created_at: "2026-10-13T00:00:00Z",
  updated_at: "2026-10-13T00:00:00Z",
};
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push, replace: mocks.replace }),
}));
vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    onNavigate,
    ...props
  }: AnchorHTMLAttributes<HTMLAnchorElement> & {
    href: string;
    children: ReactNode;
    onNavigate?: (event: { preventDefault: () => void }) => void;
  }) => (
    <a
      href={href}
      {...props}
      onClick={(event) => {
        event.preventDefault();
        onNavigate?.(event);
      }}
    >
      {children}
    </a>
  ),
}));
vi.mock("@/features/auth/useSession", () => ({
  useSession: () => ({
    token: "test",
    user: { id: 1, name: "Test" },
    bootstrapping: false,
    logout: mocks.logout,
  }),
}));
vi.mock("@/lib/api/articles", () => ({
  listArticles: async () => ({
    items: [original, { ...original, id: 2, title: "Other article" }],
    next_cursor: null,
  }),
  getArticle: async (id: number) => ({ ...original, id }),
  listVersions: async () => ({ items: [] }),
  fetchRewriteStyles: async () => ({ styles: [{ key: "genz", label: "Gen Z" }] }),
  saveArticle: (...args: unknown[]) => mocks.save(...args),
  deleteArticle: (...args: unknown[]) => mocks.remove(...args),
  generateArticle: (...args: unknown[]) => mocks.generate(...args),
  duplicateArticle: vi.fn(),
  restoreVersion: vi.fn(),
  rewriteArticle: vi.fn(),
}));

function createView(
  client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: Infinity },
      mutations: { retry: false },
    },
  }),
) {
  // These tests exercise draft transitions, not initial API loading. Keep mocked
  // snapshots ready so parallel suite load cannot delay the sidebar fixture.
  if (!client.getQueryData(["articles"]))
    client.setQueryData(["articles"], {
      pages: [
        {
          items: [original, { ...original, id: 2, title: "Other article" }],
          next_cursor: null,
        },
      ],
      pageParams: [null],
    });
  if (!client.getQueryData(["article", 1])) client.setQueryData(["article", 1], original);
  const view = render(
    <QueryClientProvider client={client}>
      <DashboardPage />
    </QueryClientProvider>,
  );
  return { ...view, client };
}
async function editArticle() {
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: /^original title/i }));
  await user.click(await screen.findByRole("button", { name: "Edit article" }));
  return user;
}

describe("workspace unsaved edits", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.remove.mockResolvedValue(undefined);
    mocks.save.mockResolvedValue({ ...original, current_version: 2 });
    Object.defineProperties(HTMLDialogElement.prototype, {
      showModal: {
        configurable: true,
        value: vi.fn(function (this: HTMLDialogElement) {
          this.setAttribute("open", "");
        }),
      },
      close: {
        configurable: true,
        value: vi.fn(function (this: HTMLDialogElement) {
          this.removeAttribute("open");
        }),
      },
    });
  });

  it("only warns for changed drafts, keeping blocked actions from spending generation calls", async () => {
    createView();
    const user = await editArticle();
    await user.click(screen.getByRole("tab", { name: "SEO Metadata" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Article" }));
    await user.click(screen.getByRole("button", { name: "Edit article" }));
    await user.type(screen.getByLabelText("Introduction"), " unsaved");
    expect(screen.getByText("Unsaved changes")).toBeVisible();
    await user.type(screen.getByLabelText("Topic / search query"), "New topic");
    await user.click(screen.getByRole("button", { name: "Generate" }));
    expect(mocks.generate).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Keep editing" }));
    expect(screen.getByLabelText("Introduction")).toHaveValue(
      "Original introduction unsaved",
    );
    await user.click(screen.getByRole("link", { name: "Website" }));
    expect(mocks.push).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Discard changes" }));
    expect(mocks.push).toHaveBeenCalledWith("/");
  });

  it("saves against the captured base version and retains a conflicted draft", async () => {
    const view = createView();
    const user = await editArticle();
    await user.type(screen.getByLabelText("Introduction"), " local edit");
    act(() =>
      view.client.setQueryData(["article", 1], {
        ...original,
        current_version: 2,
        content: { ...original.content, introduction: "New server text" },
        seo: { ...original.seo, description: "New server SEO" },
      }),
    );
    mocks.save.mockRejectedValue(
      new Error("A newer version exists; reload before saving."),
    );
    await user.click(screen.getByRole("button", { name: "Save version" }));
    await screen.findByText("A newer version exists; reload before saving.");
    expect(mocks.save).toHaveBeenCalledWith(
      1,
      1,
      expect.objectContaining({ introduction: "Original introduction local edit" }),
      original.seo,
    );
    expect(screen.getByLabelText("Introduction")).toHaveValue(
      "Original introduction local edit",
    );
    expect(screen.getByText("Unsaved changes")).toBeVisible();
  });

  it("retains drafts across route remounts and does not warn when deleting an unrelated article", async () => {
    const view = createView();
    const user = await editArticle();
    await user.type(screen.getByLabelText("Introduction"), " keep me");
    await user.click(screen.getByRole("button", { name: "Delete Other article" }));
    await waitFor(() => expect(mocks.remove).toHaveBeenCalledWith(2));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    view.unmount();
    createView(view.client);
    expect(await screen.findByLabelText("Introduction")).toHaveValue(
      "Original introduction keep me",
    );
    expect(screen.getByText("Unsaved changes")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "New article" }));
    expect(screen.getByRole("dialog")).toBeVisible();
  });

  it("blocks navigation and unload during saving, then clears only after successful save", async () => {
    let complete!: (value: ArticleDetail) => void;
    mocks.save.mockReturnValue(
      new Promise((resolve) => {
        complete = resolve;
      }),
    );
    createView();
    const user = await editArticle();
    await user.type(screen.getByLabelText("Introduction"), " saved");
    await user.click(screen.getByRole("button", { name: "Save version" }));
    expect(screen.getByText("Saving changes…")).toBeVisible();
    expect(screen.getByLabelText("Introduction")).toBeDisabled();
    expect(screen.getByRole("button", { name: "New article" })).toBeDisabled();
    await user.click(screen.getByRole("link", { name: "Website" }));
    expect(mocks.push).not.toHaveBeenCalled();
    const unload = new Event("beforeunload", { cancelable: true });
    fireEvent(window, unload);
    expect(unload.defaultPrevented).toBe(true);
    await act(async () => complete({ ...original, current_version: 2 }));
    await waitFor(() =>
      expect(screen.queryByText("Unsaved changes")).not.toBeInTheDocument(),
    );
    expect(screen.queryByText("Saving changes…")).not.toBeInTheDocument();
  });

  it("keeps a remounted workspace locked until its earlier save settles", async () => {
    let complete!: (value: ArticleDetail) => void;
    mocks.save.mockReturnValue(
      new Promise((resolve) => {
        complete = resolve;
      }),
    );
    const view = createView();
    const user = await editArticle();
    await user.type(screen.getByLabelText("Introduction"), " before back");
    await user.click(screen.getByRole("button", { name: "Save version" }));
    view.unmount();
    createView(view.client);
    expect(await screen.findByLabelText("Introduction")).toBeDisabled();
    expect(screen.getByLabelText("Introduction")).toHaveValue(
      "Original introduction before back",
    );
    expect(screen.getByText("Saving changes…")).toBeVisible();
    await user.click(screen.getByRole("link", { name: "Account" }));
    expect(mocks.push).not.toHaveBeenCalled();
    await act(async () =>
      complete({
        ...original,
        current_version: 2,
        content: {
          ...original.content,
          introduction: "Original introduction before back",
        },
      }),
    );
    expect(await screen.findByRole("button", { name: "Edit article" })).toBeEnabled();
    expect(screen.queryByText("Unsaved changes")).not.toBeInTheDocument();
    expect(view.client.getQueryData(["workspace-draft", 1])).toEqual(
      expect.objectContaining({ draft: null }),
    );
  });

  it("does not resurrect a private draft cache when a save returns after logout", async () => {
    let complete!: (value: ArticleDetail) => void;
    mocks.save.mockReturnValue(
      new Promise((resolve) => {
        complete = resolve;
      }),
    );
    const view = createView();
    const user = await editArticle();
    await user.type(screen.getByLabelText("Introduction"), " local");
    await user.click(screen.getByRole("button", { name: "Save version" }));
    view.unmount();
    view.client.clear();
    await act(async () => complete({ ...original, current_version: 2 }));
    expect(view.client.getQueryData(["workspace-draft", 1])).toBeUndefined();
    expect(view.client.getQueryData(["article", 1])).toBeUndefined();
  });
});
