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
        description="SearchScribe is a beta writing workspace. Here is what it stores and which services support it."
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
          <h2 className="font-serif text-3xl">Optional Google sign-in</h2>
          <p className="mt-3 leading-8 text-slate-600">
            If you choose Google sign-in, SearchScribe receives your verified email,
            name, and stable Google account identifier to create or identify your
            account. It does not request access to Gmail or Google Drive. Linking
            Google to an existing password account requires your password and an
            explicit linking action.
          </p>
        </section>
        <section>
          <h2 className="font-serif text-3xl">Sessions and generation</h2>
          <p className="mt-3 leading-8 text-slate-600">
            A short-lived access token and an HttpOnly refresh cookie keep you signed in.
            When you request generation or a rewrite, your topic or article content is
            sent to Google Gemini, the configured AI provider. Avoid entering sensitive personal or
            confidential information.
          </p>
        </section>
        <section>
          <h2 className="font-serif text-3xl">Account emails</h2>
          <p className="mt-3 leading-8 text-slate-600">
            Brevo sends verification, password reset, and password-change notices.
            It receives your email address, name, and the security message, including
            any single-use code. Codes are stored as hashes in SearchScribe and are
            kept out of clickable email URLs. Brevo may track email opens and clicks.
            Account emails do not subscribe you to a marketing list.
          </p>
        </section>
        <section>
          <h2 className="font-serif text-3xl">Hosting and beta limitations</h2>
          <p className="mt-3 leading-8 text-slate-600">
            Vercel hosts the website, Render runs the API, and Neon stores account
            and article data in Postgres. Self-service account deletion and a
            published retention schedule are not yet available. You can inspect the current
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
