/** Public catalogue IDs occupy a persisted range outside RomM's identity space. */
export function isPublicCatalogueRom(romId: number | null | undefined): boolean {
  return romId != null && romId >= 2 ** 52;
}
