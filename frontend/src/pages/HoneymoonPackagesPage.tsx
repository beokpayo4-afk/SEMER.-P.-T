import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ErrorMessage } from "../components/ErrorMessage.tsx";
import { Loading } from "../components/Loading.tsx";
import { ProductImage } from "../components/ProductImage.tsx";
import { usePageTitle } from "../hooks/usePageTitle.ts";
import {
  listTravel,
  travelDurationLabel,
  type PackageType,
  type TravelPackage,
} from "../services/travel.ts";
import { apiErrorMessage } from "../utils/errors.ts";
import { formatPaise } from "../utils/money.ts";

const description = "Discover beautiful honeymoon destinations, romantic stays and memorable experiences.";

export function HoneymoonPackagesPage() {
  const [params, setParams] = useSearchParams();
  const packageType: PackageType = params.get("type") === "international" ? "international" : "domestic";
  usePageTitle("Honeymoon Packages", {
    description,
    image: "/images/travel/honeymoon.png",
  });
  const [packages, setPackages] = useState<TravelPackage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    listTravel({
      category: "honeymoon",
      package_type: packageType,
      package_category: "honeymoon",
      page: 1,
      page_size: 24,
    })
      .then((result) => {
        if (!active) {
          return;
        }
        setPackages(result.items);
        setError("");
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(apiErrorMessage(reason, "Travel packages could not be loaded."));
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [packageType]);

  function setPackageType(next: PackageType) {
    const following = new URLSearchParams(params);
    following.set("type", next);
    setParams(following);
  }

  return (
    <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16">
      <p className="text-xs tracking-[0.18em] text-muted uppercase">Travel</p>
      <h1 className="mt-3 max-w-3xl text-4xl sm:text-5xl">Honeymoon Packages</h1>
      <p className="mt-4 text-lg">Romantic Escapes for Two</p>
      <p className="mt-3 max-w-2xl leading-7 text-muted">{description}</p>
      <div className="mt-8 grid gap-3 sm:grid-cols-2" role="tablist" aria-label="Honeymoon type">
        <TypeTab active={packageType === "domestic"} label="🇮🇳 Domestic" onClick={() => setPackageType("domestic")} />
        <TypeTab
          active={packageType === "international"}
          label="🌎 International"
          onClick={() => setPackageType("international")}
        />
      </div>
      {loading ? <Loading label="Loading packages" /> : null}
      {error ? (
        <div className="mt-6">
          <ErrorMessage message={error} />
        </div>
      ) : null}
      {!loading && !error && packages.length === 0 ? (
        <p className="mt-8 text-muted">Packages will appear here when they are published.</p>
      ) : null}
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {packages.map((item) => (
          <article key={item.id} className="overflow-hidden rounded-3xl border border-line bg-white">
            <Link to={`/travel/honeymoon/${item.slug}`}>
              <ProductImage
                src={item.images[0]?.url}
                alt={item.images[0]?.alt_text || item.title}
                className="aspect-4/3 w-full"
              />
            </Link>
            <div className="p-5">
              <div className="flex flex-wrap gap-2">
                <span className="rounded-full bg-sand px-2.5 py-1 text-[11px] tracking-[0.14em] uppercase">Honeymoon</span>
                <span className="rounded-full border border-line px-2.5 py-1 text-[11px] tracking-[0.14em] uppercase">
                  {item.package_type === "international" ? "International" : "Domestic"}
                </span>
              </div>
              <h2 className="mt-3 text-2xl">{item.title}</h2>
              <p className="mt-2 text-sm text-muted">
                {honeymoonPlace(item)} · {travelDurationLabel(item.duration, item.category)}
              </p>
              <p className="mt-3 text-sm">From {formatPaise(item.starting_price)}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link
                  to={`/travel/honeymoon/${item.slug}`}
                  className="rounded-full bg-ink px-4 py-2 text-sm text-paper"
                >
                  View package
                </Link>
                <Link
                  to={`/travel/enquire?package=${item.id}`}
                  className="rounded-full border border-line px-4 py-2 text-sm"
                >
                  Enquire
                </Link>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export function honeymoonPlace(item: Pick<TravelPackage, "destination" | "country" | "package_type">) {
  if (item.package_type === "domestic" || item.destination.toLowerCase().includes(item.country.toLowerCase())) {
    return item.destination;
  }
  return `${item.destination}, ${item.country}`;
}

function TypeTab({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`rounded-full px-5 py-3 text-sm sm:text-base ${active ? "bg-ink text-paper" : "border border-line bg-white"}`}
    >
      {label}
    </button>
  );
}
