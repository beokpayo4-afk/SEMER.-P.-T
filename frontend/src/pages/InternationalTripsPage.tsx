import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ErrorMessage } from "../components/ErrorMessage.tsx";
import { Loading } from "../components/Loading.tsx";
import { ProductImage } from "../components/ProductImage.tsx";
import { usePageTitle } from "../hooks/usePageTitle.ts";
import {
  listTravel,
  travelDurationLabel,
  travelPlaceLabel,
  type TravelPackage,
} from "../services/travel.ts";
import { apiErrorMessage } from "../utils/errors.ts";
import { formatPaise } from "../utils/money.ts";

const description = "Discover unforgettable international holiday experiences.";

export function InternationalTripsPage() {
  usePageTitle("International Trips", {
    description,
    image: "/images/travel/international.png",
  });
  const [packages, setPackages] = useState<TravelPackage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    listTravel({ category: "international", page: 1, page_size: 24 })
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
  }, []);

  return (
    <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16">
      <p className="text-xs tracking-[0.18em] text-muted uppercase">Travel</p>
      <h1 className="mt-3 max-w-3xl text-4xl sm:text-5xl">International Trips</h1>
      <p className="mt-4 max-w-2xl leading-7 text-muted">{description}</p>
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
          <Link
            key={item.id}
            to={`/travel/international/${item.slug}`}
            className="overflow-hidden rounded-3xl border border-line bg-white transition hover:border-ink"
          >
            <ProductImage
              src={item.images[0]?.url}
              alt={item.images[0]?.alt_text || item.title}
              className="aspect-4/3 w-full"
            />
            <div className="p-5">
              <p className="text-xs tracking-[0.14em] text-muted uppercase">International Trips</p>
              <h2 className="mt-2 text-2xl">{item.title}</h2>
              <p className="mt-2 text-sm text-muted">
                {travelPlaceLabel(item.destination, item.country, item.category)} · {travelDurationLabel(item.duration, item.category)}
              </p>
              <p className="mt-3 text-sm">From {formatPaise(item.starting_price)}</p>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
