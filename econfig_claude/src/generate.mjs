// Spec -> CFR.
//
// A spec names a template configuration and the feature codes it wants changed.
// Templates matter: a .cfr produced by the real configurator already carries a
// valid document header, locale, price-file date and engine metadata, and its
// products already include the mandatory companion features the engine added.
// Starting from one and editing the feature set is far likelier to survive
// reconcile than assembling a document from nothing.
//
// Nothing here judges compatibility - see the caveats in README.

import { decode, encode, listProducts } from './codec.mjs';

const FEATURE_DEFAULTS = {
  num: '',
  reference_notes_num: '',
  vrm_text: '',
  release: '',
  mod: '',
  price_flag: 'Y',
  description: '',
  quantity: 1,
};

const mtmOf = (p) => [p.type, p.model].filter(Boolean).join('-');

/** Accepts `{"EM54": 6}` or `{"EM54": {qty: 6, description: "..."}}`. */
function normaliseFeature(code, value) {
  if (value == null) throw new Error(`feature ${code}: missing quantity`);
  const spec = typeof value === 'object' ? value : { qty: value };
  const qty = Number(spec.qty ?? spec.quantity);
  if (!Number.isInteger(qty) || qty < 0) {
    throw new Error(`feature ${code}: quantity must be a non-negative integer, got ${JSON.stringify(value)}`);
  }
  return { code: String(code).toUpperCase(), qty, description: spec.description };
}

/**
 * Apply a spec to a template CFR.
 *
 * spec = {
 *   description?: string,                       // written to cfreport_description
 *   products: [{
 *     mtm: "9824-42A",
 *     index?: number,                           // when the template repeats an MTM
 *     mode?: "merge" | "replace",               // default merge
 *     quantity?: number,                        // product-level quantity
 *     features: { EM54: 6, ECW0: 0, EB46: {qty: 8, description: "..."} }
 *   }]
 * }
 *
 * merge   - listed codes are set, 0 removes, everything else is left alone
 * replace - the feature set becomes exactly what is listed
 */
export function generate(spec, templateText) {
  if (!spec || !Array.isArray(spec.products) || !spec.products.length) {
    throw new Error('spec must contain a non-empty "products" array');
  }
  const json = decode(templateText);
  const report = { products: [], warnings: [] };

  for (const want of spec.products) {
    if (!want.mtm) throw new Error('every spec product needs an "mtm"');
    const mtm = String(want.mtm).toUpperCase();
    const mode = want.mode ?? 'merge';
    if (mode !== 'merge' && mode !== 'replace') {
      throw new Error(`${mtm}: mode must be "merge" or "replace"`);
    }

    const matches = Object.entries(json.products).filter(([, p]) => mtmOf(p).toUpperCase() === mtm);
    if (!matches.length) {
      const available = [...new Set(Object.values(json.products).map(mtmOf))].join(', ');
      throw new Error(
        `${mtm} is not in the template. The template holds: ${available}. ` +
          `Pick a template that already contains ${mtm}.`,
      );
    }
    const pick = want.index ?? 0;
    if (pick >= matches.length) {
      throw new Error(`${mtm}: index ${pick} out of range, template has ${matches.length}`);
    }
    const [uid, product] = matches[pick];

    const wanted = Object.entries(want.features ?? {}).map(([c, v]) => normaliseFeature(c, v));
    const known = new Map(product.features.map((f) => [f.num.toUpperCase(), f]));
    const applied = [];

    if (mode === 'replace') {
      product.features = wanted
        .filter((w) => w.qty > 0)
        .map((w) => {
          const prev = known.get(w.code);
          if (!prev && !w.description) {
            report.warnings.push(`${mtm} ${w.code}: new code with no description - engine must fill it in`);
          }
          applied.push({ code: w.code, from: prev?.quantity ?? 0, to: w.qty });
          return { ...FEATURE_DEFAULTS, ...prev, num: w.code, quantity: w.qty,
                   description: w.description ?? prev?.description ?? '' };
        });
      for (const [code, f] of known) {
        if (!wanted.some((w) => w.code === code && w.qty > 0)) {
          applied.push({ code, from: f.quantity, to: 0 });
        }
      }
    } else {
      for (const w of wanted) {
        const prev = known.get(w.code);
        if (w.qty === 0) {
          if (!prev) continue;
          product.features = product.features.filter((f) => f.num.toUpperCase() !== w.code);
          applied.push({ code: w.code, from: prev.quantity, to: 0 });
        } else if (prev) {
          applied.push({ code: w.code, from: prev.quantity, to: w.qty });
          prev.quantity = w.qty;
          if (w.description) prev.description = w.description;
        } else {
          if (!w.description) {
            report.warnings.push(`${mtm} ${w.code}: new code with no description - engine must fill it in`);
          }
          product.features.push({ ...FEATURE_DEFAULTS, num: w.code, quantity: w.qty,
                                  description: w.description ?? '' });
          applied.push({ code: w.code, from: 0, to: w.qty });
        }
      }
    }

    if (want.quantity != null) {
      applied.push({ code: '(product)', from: product.quantity, to: want.quantity });
      product.quantity = want.quantity;
    }
    if (want.description) product.description = want.description;

    report.products.push({ mtm, uid, mode, applied: applied.filter((a) => a.from !== a.to) });
  }

  if (spec.description) json.document_info.cfreport_description = spec.description;

  return { cfr: encode(json), report };
}

/** Produce a spec skeleton from an existing configuration, ready to edit. */
export function specFromCfr(text, { templateName = 'template.cfr' } = {}) {
  const products = listProducts(decode(text));
  return {
    template: templateName,
    description: '',
    products: products.map((p) => ({
      mtm: p.mtm,
      mode: 'merge',
      features: Object.fromEntries(p.features.map((f) => [f.code, f.quantity])),
    })),
  };
}
