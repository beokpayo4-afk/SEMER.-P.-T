import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ErrorMessage } from "../components/ErrorMessage.tsx";
import { Loading } from "../components/Loading.tsx";
import { ProductImage } from "../components/ProductImage.tsx";
import { usePageTitle } from "../hooks/usePageTitle.ts";
import {
  getTravelPackage,
  getTravelPackageBySlug,
  travelCategoryLabel,
  travelDurationLabel,
  travelPlaceLabel,
  type TravelPackage,
} from "../services/travel.ts";
import { apiErrorMessage } from "../utils/errors.ts";
import { formatPaise } from "../utils/money.ts";
import { isUuid } from "../utils/product.ts";

export function TravelDetailPage() {
  const { id = "", slug = "" } = useParams();
  const validId = isUuid(id);
  const validSlug = /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug);
  const lookup = slug ? (validSlug ? slug : "") : validId ? id : "";
  const [travelPackage, setTravelPackage] = useState<TravelPackage | null>(null);
  const [loading, setLoading] = useState(Boolean(lookup));
  const [error, setError] = useState("");
  const international = travelPackage?.category === "international";
  usePageTitle(travelPackage?.title ?? "Travel package", {
    description: travelPackage?.description,
    image: travelPackage?.images[0]?.url,
  });

  useEffect(() => {
    if (!lookup) {
      return;
    }
    let active = true;
    setLoading(true);
    const request = slug ? getTravelPackageBySlug(lookup) : getTravelPackage(lookup);
    request
      .then((next) => {
        if (active) {
          setTravelPackage(next);
          setError("");
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setTravelPackage(null);
          setError(apiErrorMessage(reason, "Package not found."));
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
  }, [lookup, slug]);

  if (!lookup || (!loading && (error || !travelPackage))) {
    return (
      <section className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
        <ErrorMessage message="Package not found." />
        <Link to="/travel" className="mt-4 inline-block text-wine">
          Back to travel
        </Link>
      </section>
    );
  }

  if (loading || !travelPackage) {
    return (
      <section className="mx-auto max-w-5xl px-4 sm:px-6">
        <Loading label="Loading package" />
      </section>
    );
  }

  const image = travelPackage.images[0];
  const sections = [
    ["Itinerary", travelPackage.itinerary],
    ["Accommodation", travelPackage.accommodation],
    ["Transportation", travelPackage.transportation],
    ["Activities", travelPackage.activities],
    ["Inclusions", travelPackage.inclusions],
    ["Exclusions", travelPackage.exclusions],
  ].filter(([, text]) => text);

  const backTo = international
    ? "/travel/international"
    : travelPackage.category === "holiday"
      ? `/travel?category=holiday&type=${travelPackage.package_type}`
      : "/travel";

  return (
    <article className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 sm:py-16 lg:grid-cols-[1.1fr_0.9fr]">
      <div className={international ? "order-2 lg:order-1" : undefined}>
        <Link to={backTo} className="text-sm text-muted">
          {international ? "International Trips" : travelPackage.category === "holiday" ? "Holiday Packages" : "Travel"}
        </Link>
        <p className="mt-4 text-xs tracking-[0.14em] text-muted uppercase">
          {travelCategoryLabel(travelPackage.category)}
        </p>
        <h1 className="mt-2 text-4xl sm:text-5xl">{travelPackage.title}</h1>
        <p className="mt-4 text-lg leading-8 text-muted">{travelPackage.description}</p>
        <dl className="mt-6 grid gap-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted">Destination</dt>
            <dd>{travelPlaceLabel(travelPackage.destination, travelPackage.country, travelPackage.category)}</dd>
          </div>
          <div>
            <dt className="text-muted">Duration</dt>
            <dd>{travelDurationLabel(travelPackage.duration, travelPackage.category)}</dd>
          </div>
          <div>
            <dt className="text-muted">Starting price</dt>
            <dd>{formatPaise(travelPackage.starting_price)}</dd>
          </div>
        </dl>
        <div className="mt-8 space-y-6">
          {sections.map(([title, text]) => (
            <section key={title}>
              <h2 className="text-2xl">{title}</h2>
              <p className="mt-2 whitespace-pre-line leading-7">{text}</p>
            </section>
          ))}
        </div>
      </div>
      <div className={international ? "order-1 lg:order-2" : undefined}>
        <ProductImage
          src={image?.url}
          alt={image?.alt_text || travelPackage.title}
          className="aspect-4/3 w-full rounded-3xl"
        />
        <Link
          to={`/travel/enquire?package=${travelPackage.id}`}
          className="mt-6 inline-flex rounded-full bg-wine px-5 py-2.5 text-sm text-paper"
        >
          Enquire
        </Link>
        <p className="mt-3 text-sm text-muted">The starting price is confirmed with a quote after your enquiry.</p>
      </div>
    </article>
  );
}
