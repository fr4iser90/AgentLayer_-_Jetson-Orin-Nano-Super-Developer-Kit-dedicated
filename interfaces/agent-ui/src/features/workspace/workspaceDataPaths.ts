/** Supports top-level keys (`pets`) and dotted paths (`albums.0.photos`) for nested albums. */
export function getPath(obj: Record<string, unknown>, path: string): unknown {
  if (!path.includes(".")) {
    return obj[path];
  }
  const segs = path.split(".").filter(Boolean);
  let cur: unknown = obj;
  for (const seg of segs) {
    if (cur === null || cur === undefined) return undefined;
    if (Array.isArray(cur)) {
      const i = Number(seg);
      if (!Number.isInteger(i) || i < 0 || i >= cur.length) return undefined;
      cur = cur[i];
    } else if (typeof cur === "object") {
      cur = (cur as Record<string, unknown>)[seg];
    } else {
      return undefined;
    }
  }
  return cur;
}

export function setPath(
  obj: Record<string, unknown>,
  path: string,
  value: unknown
): Record<string, unknown> {
  if (!path.includes(".")) {
    return { ...obj, [path]: value };
  }
  const segs = path.split(".").filter(Boolean);
  const [head, ...tail] = segs;
  const tailPath = tail.join(".");
  const raw = obj[head];

  if (Array.isArray(raw)) {
    const idx = Number(tail[0]);
    if (!Number.isInteger(idx) || idx < 0) {
      return { ...obj, [head]: value };
    }
    const arr = [...raw];
    if (tail.length === 1) {
      arr[idx] = value;
      return { ...obj, [head]: arr };
    }
    const elem = arr[idx];
    const inner =
      elem !== null && typeof elem === "object" && !Array.isArray(elem)
        ? { ...(elem as Record<string, unknown>) }
        : {};
    arr[idx] = setPath(inner, tail.slice(1).join("."), value);
    return { ...obj, [head]: arr };
  }

  const child =
    raw !== null && typeof raw === "object" && !Array.isArray(raw)
      ? { ...(raw as Record<string, unknown>) }
      : {};
  return { ...obj, [head]: setPath(child, tailPath, value) };
}
