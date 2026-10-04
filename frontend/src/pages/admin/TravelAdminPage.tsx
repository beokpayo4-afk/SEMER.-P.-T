import { type FormEvent, useEffect, useState } from "react";
import { ImageField } from "../../components/admin/ImageField.tsx";
import { Button } from "../../components/Button.tsx";
import { ErrorMessage } from "../../components/ErrorMessage.tsx";
import { Input } from "../../components/Input.tsx";
import { Loading } from "../../components/Loading.tsx";
import { Select } from "../../components/Select.tsx";
import { usePageTitle } from "../../hooks/usePageTitle.ts";
import { useToast } from "../../hooks/useToast.ts";
import { adminTravel, deleteTravel, saveTravel, type TravelInput } from "../../services/admin.ts";
import { api } from "../../services/api.ts";
import {
  packageCategories,
  travelCategories,
  type PackageCategory,
  type PackageType,
  type TravelCategory,
  type TravelPackage,
} from "../../services/travel.ts";
import { apiErrorMessage } from "../../utils/errors.ts";
import { formatPaise, rupeesToPaise } from "../../utils/money.ts";

const empty = {
  title: "",
  slug: "",
  category: "domestic" as TravelCategory,
  packageType: "domestic" as PackageType,
  packageCategory: "" as "" | PackageCategory,
  destination: "",
  country: "India",
  duration: "3",
  price: "",
  description: "",
  itinerary: "",
  inclusions: "",
  exclusions: "",
  romanticHighlights: "",
  hotelCategory: "",
  roomType: "",
  coupleExperiences: "",
  honeymoonInclusions: "",
  status: "draft" as TravelInput["status"],
  featured: false,
  imageUrl: "",
  gallery: [] as string[],
};

export function TravelAdminPage() {
  usePageTitle("Admin travel");
  const [packages, setPackages] = useState<TravelPackage[]>([]);
  const [form, setForm] = useState(empty);
  const [editing, setEditing] = useState<string | null>(null);
  const [current, setCurrent] = useState<TravelPackage | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [uploadingGallery, setUploadingGallery] = useState(false);
  const { showToast } = useToast();

  function load() {
    setLoading(true);
    adminTravel()
      .then((result) => {
        setPackages(result.items);
        setError("");
      })
      .catch((reason: unknown) => setError(apiErrorMessage(reason, "Packages could not be loaded.")))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
  }, []);

  function edit(item: TravelPackage) {
    setEditing(item.id);
    setCurrent(item);
    setForm({
      title: item.title,
      slug: item.slug,
      category: item.category,
      packageType: item.package_type,
      packageCategory: item.package_category ?? "",
      destination: item.destination,
      country: item.country,
      duration: String(item.duration),
      price: String(item.starting_price / 100),
      description: item.description,
      itinerary: item.itinerary,
      inclusions: item.inclusions,
      exclusions: item.exclusions,
      romanticHighlights: item.romantic_highlights,
      hotelCategory: item.hotel_category,
      roomType: item.room_type,
      coupleExperiences: item.couple_experiences,
      honeymoonInclusions: item.honeymoon_inclusions,
      status: item.status,
      featured: item.featured,
      imageUrl: item.images[0]?.url ?? "",
      gallery: item.images.slice(1).map((image) => image.url),
    });
  }

  function chooseCategory(category: TravelCategory) {
    const packageCategory =
      category === "holiday" || category === "honeymoon" ? category : form.packageCategory;
    setForm({ ...form, category, packageCategory });
  }

  async function uploadGallery(file: File | undefined) {
    if (!file) {
      return;
    }
    const body = new FormData();
    body.append("file", file);
    setUploadingGallery(true);
    try {
      const { data } = await api.post<{ url: string }>("/api/admin/uploads/travel", body);
      setForm((currentForm) => ({ ...currentForm, gallery: [...currentForm.gallery, data.url] }));
    } catch (reason: unknown) {
      showToast(apiErrorMessage(reason, "The image could not be uploaded."));
    } finally {
      setUploadingGallery(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const starting = rupeesToPaise(form.price);
    const duration = Number(form.duration);
    if (starting === undefined || !Number.isInteger(duration) || duration < 1) {
      setError("Enter a duration and a starting price in rupees.");
      return;
    }
    const images = [
      ...(form.imageUrl.trim() ? [{ url: form.imageUrl.trim(), alt_text: form.title, sort_order: 0 }] : []),
      ...form.gallery
        .map((url) => url.trim())
        .filter(Boolean)
        .map((url, index) => ({ url, alt_text: form.title, sort_order: index + 1 })),
    ];
    const savedImages = images.length
      ? images
      : current?.images.map((image) => ({ url: image.url, alt_text: image.alt_text, sort_order: image.sort_order })) ?? [];
    try {
      await saveTravel(
        {
          title: form.title,
          slug: form.slug,
          category: form.category,
          package_type: form.packageType,
          package_category: form.packageCategory || null,
          destination: form.destination,
          country: form.country,
          duration,
          starting_price: starting,
          description: form.description,
          itinerary: form.itinerary,
          accommodation: current?.accommodation ?? "",
          transportation: current?.transportation ?? "",
          activities: current?.activities ?? "",
          inclusions: form.inclusions,
          exclusions: form.exclusions,
          romantic_highlights: form.romanticHighlights,
          hotel_category: form.hotelCategory,
          room_type: form.roomType,
          couple_experiences: form.coupleExperiences,
          honeymoon_inclusions: form.honeymoonInclusions,
          images: savedImages,
          status: form.status,
          featured: form.featured,
        },
        editing ?? undefined,
      );
      setForm(empty);
      setEditing(null);
      setCurrent(null);
      load();
    } catch (reason: unknown) {
      setError(apiErrorMessage(reason, "The package could not be saved."));
    }
  }

  async function remove(item: TravelPackage) {
    if (!window.confirm(`Delete ${item.title}?`)) {
      return;
    }
    try {
      await deleteTravel(item.id);
      load();
    } catch (reason: unknown) {
      setError(apiErrorMessage(reason, "The package could not be deleted."));
    }
  }

  return (
    <section className="px-4 py-8 sm:px-6">
      <h1 className="text-4xl">Travel</h1>
      <form onSubmit={(event) => void submit(event)} className="mt-6 grid max-w-3xl gap-4">
        {error ? <ErrorMessage message={error} /> : null}
        <Input label="Title" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} required />
        <Input label="Slug" value={form.slug} onChange={(event) => setForm({ ...form, slug: event.target.value })} required />
        <Select
          label="Category"
          value={form.category}
          onChange={(event) => chooseCategory(event.target.value as TravelCategory)}
          options={travelCategories.map((item) => ({ value: item.value, label: item.label }))}
        />
        <Select
          label="Package category"
          value={form.packageCategory}
          onChange={(event) => setForm({ ...form, packageCategory: event.target.value as "" | PackageCategory })}
          options={[{ value: "", label: "None" }, ...packageCategories.map((item) => ({ value: item.value, label: item.label }))]}
        />
        {form.category === "holiday" || form.category === "honeymoon" ? (
          <fieldset className="grid gap-2 text-sm">
            <legend className="font-medium">Package type</legend>
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="packageType"
                checked={form.packageType === "domestic"}
                onChange={() => setForm({ ...form, packageType: "domestic" })}
              />
              Domestic
            </label>
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="packageType"
                checked={form.packageType === "international"}
                onChange={() => setForm({ ...form, packageType: "international" })}
              />
              International
            </label>
          </fieldset>
        ) : null}
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Destination" value={form.destination} onChange={(event) => setForm({ ...form, destination: event.target.value })} required />
          <Input label="Country" value={form.country} onChange={(event) => setForm({ ...form, country: event.target.value })} required />
          <Input label="Duration (days)" value={form.duration} onChange={(event) => setForm({ ...form, duration: event.target.value })} required />
          <Input label="Starting price (₹)" value={form.price} onChange={(event) => setForm({ ...form, price: event.target.value })} required />
        </div>
        <label className="block text-sm">
          <span className="mb-1.5 block font-medium">Description</span>
          <textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} rows={3} className="w-full rounded-xl border border-line px-3 py-2" required />
        </label>
        <label className="block text-sm">
          <span className="mb-1.5 block font-medium">Itinerary</span>
          <textarea value={form.itinerary} onChange={(event) => setForm({ ...form, itinerary: event.target.value })} rows={8} className="w-full rounded-xl border border-line px-3 py-2" />
        </label>
        <label className="block text-sm">
          <span className="mb-1.5 block font-medium">Inclusions</span>
          <textarea value={form.inclusions} onChange={(event) => setForm({ ...form, inclusions: event.target.value })} rows={4} className="w-full rounded-xl border border-line px-3 py-2" />
        </label>
        <label className="block text-sm">
          <span className="mb-1.5 block font-medium">Exclusions</span>
          <textarea value={form.exclusions} onChange={(event) => setForm({ ...form, exclusions: event.target.value })} rows={4} className="w-full rounded-xl border border-line px-3 py-2" />
        </label>
        {form.category === "honeymoon" ? (
          <>
            <label className="block text-sm">
              <span className="mb-1.5 block font-medium">Romantic highlights</span>
              <textarea value={form.romanticHighlights} onChange={(event) => setForm({ ...form, romanticHighlights: event.target.value })} rows={4} className="w-full rounded-xl border border-line px-3 py-2" />
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <Input label="Hotel category" value={form.hotelCategory} onChange={(event) => setForm({ ...form, hotelCategory: event.target.value })} />
              <Input label="Room type" value={form.roomType} onChange={(event) => setForm({ ...form, roomType: event.target.value })} />
            </div>
            <label className="block text-sm">
              <span className="mb-1.5 block font-medium">Couple experiences</span>
              <textarea value={form.coupleExperiences} onChange={(event) => setForm({ ...form, coupleExperiences: event.target.value })} rows={4} className="w-full rounded-xl border border-line px-3 py-2" />
            </label>
            <label className="block text-sm">
              <span className="mb-1.5 block font-medium">Honeymoon inclusions</span>
              <textarea value={form.honeymoonInclusions} onChange={(event) => setForm({ ...form, honeymoonInclusions: event.target.value })} rows={4} className="w-full rounded-xl border border-line px-3 py-2" />
            </label>
          </>
        ) : null}
        <ImageField folder="travel" value={form.imageUrl} onChange={(url) => setForm({ ...form, imageUrl: url })} />
        <div className="text-sm">
          <span className="mb-1.5 block font-medium">Gallery</span>
          <label className="block">
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
              disabled={uploadingGallery}
              onChange={(event) => {
                void uploadGallery(event.target.files?.[0]);
                event.target.value = "";
              }}
            />
            <span className="mt-1 block text-muted">{uploadingGallery ? "Uploading" : "Add another destination photo."}</span>
          </label>
          {form.gallery.length > 0 ? (
            <ul className="mt-3 space-y-2">
              {form.gallery.map((url) => (
                <li key={url} className="flex items-center justify-between gap-3">
                  <span className="truncate text-muted">{url}</span>
                  <button
                    type="button"
                    className="text-wine"
                    onClick={() => setForm({ ...form, gallery: form.gallery.filter((item) => item !== url) })}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        <Select
          label="Status"
          value={form.status}
          onChange={(event) => setForm({ ...form, status: event.target.value as TravelInput["status"] })}
          options={[
            { value: "draft", label: "Draft" },
            { value: "active", label: "Active" },
            { value: "archived", label: "Archived" },
          ]}
        />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.featured} onChange={(event) => setForm({ ...form, featured: event.target.checked })} />
          Featured
        </label>
        <Button type="submit">{editing ? "Update package" : "Add package"}</Button>
      </form>
      {loading ? <Loading label="Loading packages" /> : null}
      <ul className="mt-6 divide-y divide-line rounded-3xl border border-line bg-white">
        {packages.map((item) => (
          <li key={item.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm">
            <div>
              <p>{item.title}</p>
              <p className="text-muted">
                {item.status}
                {item.category === "holiday" || item.category === "honeymoon"
                  ? ` · ${item.package_type === "international" ? "International" : "Domestic"}`
                  : ""} · From {formatPaise(item.starting_price)}
              </p>
            </div>
            <div className="space-x-3">
              <button type="button" className="text-wine" onClick={() => edit(item)}>
                Edit
              </button>
              <button type="button" className="text-wine" onClick={() => void remove(item)}>
                Delete
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
