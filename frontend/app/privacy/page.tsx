import type { Metadata } from "next";
import SiteChrome from "@/components/marketing/SiteChrome";
import PageHeading from "@/components/marketing/PageHeading";

export const metadata: Metadata = {
  title: "Privacy | SearchScribe",
  description: "What the SearchScribe beta stores and where to find its implementation.",
};

export default function PrivacyPage() {
  return (
    <SiteChrome>
      <PageHeading
        eyebrow="Privacy information"
        title="Know what your workspace keeps."
        description="This beta is still being prepared for a verified public launch. The details below describe the application design; production hosting and retention details will be confirmed before release."
      />
      <div className="mx-auto max-w-3xl space-y-10 px-5 py-16 sm:px-8">
        <section>
          <h2 className="font-serif text-3xl">Account and articles</h2>
          <p className="mt-3 leading-8 text-slate-600">
            The application stores your account details, article content, SEO fields, and
            version history in its database so you can return to your work. Passwords are
            stored as hashes, not readable passwords.
          </p>
        </section>
        <section>
          <h2 className="font-serif text-3xl">Sessions and generation</h2>
          <p className="mt-3 leading-8 text-slate-600">
            A short-lived access token and an HttpOnly refresh cookie keep you signed in.
            When you request generation or a rewrite, your topic or article content is
            sent to the configured AI provider. Avoid entering sensitive personal or
            confidential information.
          </p>
        </section>
        <section>
          <h2 className="font-serif text-3xl">Before public launch</h2>
          <p className="mt-3 leading-8 text-slate-600">
            We will publish confirmed hosting, retention, deletion, and contact details
            after the production stack is verified. You can inspect the current
            implementation and raise questions in the{" "}
            <a
              className="underline hover:text-teal-800"
              href="https://github.com/abhay-yemekar/SearchScribe_AI_Studio"
            >
              open-source repository
            </a>
            .
          </p>
        </section>
      </div>
    </SiteChrome>
  );
}
