/* @ds-bundle: {"format":3,"namespace":"AsgardDesignSystem_d84b02","components":[{"name":"Badge","sourcePath":"components/core/Badge.jsx"},{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Card","sourcePath":"components/core/Card.jsx"},{"name":"Input","sourcePath":"components/forms/Input.jsx"},{"name":"Toggle","sourcePath":"components/forms/Toggle.jsx"},{"name":"NavPills","sourcePath":"components/navigation/NavPills.jsx"},{"name":"KpiStat","sourcePath":"components/trading/KpiStat.jsx"},{"name":"SignalCard","sourcePath":"components/trading/SignalCard.jsx"},{"name":"Ticker","sourcePath":"components/trading/Ticker.jsx"}],"sourceHashes":{"components/core/Badge.jsx":"f8259c52b3e4","components/core/Button.jsx":"855c0f699a8d","components/core/Card.jsx":"c76aaf55d308","components/forms/Input.jsx":"a2f630446c9e","components/forms/Toggle.jsx":"7c8a5facdd8c","components/navigation/NavPills.jsx":"621f97f72bc3","components/trading/KpiStat.jsx":"eb748506f02e","components/trading/SignalCard.jsx":"636c4f43ad04","components/trading/Ticker.jsx":"57617770dcb9","ui_kits/terminal/Screens.jsx":"74437a7780af","ui_kits/terminal/Views.jsx":"de3b81445f6b","ui_kits/terminal/data.js":"45fd13810e90"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.AsgardDesignSystem_d84b02 = window.AsgardDesignSystem_d84b02 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Badge.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const TONES = {
  blue: ['var(--blue-bg)', 'var(--blue)', 'var(--blue-bd)'],
  purple: ['var(--pu-bg)', 'var(--pu)', 'var(--pu-bd)'],
  green: ['var(--gr-bg)', 'var(--gr)', 'var(--gr-bd)'],
  red: ['var(--re-bg)', 'var(--re)', 'var(--re-bd)'],
  gold: ['var(--gold-bg)', 'var(--gold)', 'var(--gold-bd)'],
  neutral: ['var(--s2)', 'var(--t2)', 'var(--bd)']
};

/**
 * Asgard badge / chip / tag — a small pill label. Use for statuses
 * (Configured, Active), directions (BUY/SELL) and live indicators.
 */
function Badge({
  tone = 'neutral',
  bordered = true,
  dot = false,
  children,
  style = {},
  ...rest
}) {
  const [bg, fg, bd] = TONES[tone] || TONES.neutral;
  return /*#__PURE__*/React.createElement("span", _extends({}, rest, {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 5,
      background: bg,
      color: fg,
      border: bordered ? `1px solid ${bd}` : 'none',
      padding: '2px 8px',
      borderRadius: 'var(--rp)',
      fontFamily: 'var(--font-sans)',
      fontSize: 9.5,
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      lineHeight: 1.6,
      ...style
    }
  }), dot && /*#__PURE__*/React.createElement("span", {
    style: {
      width: 5,
      height: 5,
      borderRadius: '50%',
      background: fg
    }
  }), children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Badge.jsx", error: String((e && e.message) || e) }); }

// components/core/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const VARIANTS = {
  primary: {
    background: 'var(--blue)',
    color: '#fff',
    glow: 'var(--glow-blue)'
  },
  buy: {
    background: 'var(--gr)',
    color: '#fff',
    glow: 'var(--glow-gr)'
  },
  sell: {
    background: 'var(--re)',
    color: '#fff',
    glow: 'var(--glow-re)'
  },
  danger: {
    background: 'var(--re)',
    color: '#fff',
    glow: 'var(--glow-re)'
  }
};

/**
 * Asgard primary action button. Pill-shaped, uppercase, with a colored
 * glow + lift on hover. Use `ghost` for low-emphasis secondary actions.
 */
function Button({
  variant = 'primary',
  ghost = false,
  size = 'md',
  disabled = false,
  icon = null,
  children,
  style = {},
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const v = VARIANTS[variant] || VARIANTS.primary;
  const pad = size === 'sm' ? '7px 14px' : size === 'lg' ? '13px 22px' : '11px 18px';
  const fs = size === 'sm' ? 11 : 13;
  const base = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 7,
    padding: pad,
    fontFamily: 'var(--font-sans)',
    fontSize: fs,
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    lineHeight: 1,
    borderRadius: 'var(--rp)',
    cursor: disabled ? 'default' : 'pointer',
    transition: 'all var(--dur-base) var(--ease)',
    outline: 'none',
    ...style
  };
  const skin = ghost ? {
    background: 'transparent',
    color: 'var(--t2)',
    border: '1px solid var(--bd)',
    ...(hover && !disabled ? {
      background: 'var(--s3)',
      color: 'var(--t1)',
      borderColor: 'var(--bd-h)'
    } : {})
  } : {
    background: v.background,
    color: v.color,
    border: 'none',
    ...(hover && !disabled ? {
      boxShadow: v.glow,
      transform: 'translateY(-1px)'
    } : {})
  };
  return /*#__PURE__*/React.createElement("button", _extends({}, rest, {
    disabled: disabled,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      ...base,
      ...skin,
      ...(disabled ? {
        opacity: 0.5,
        transform: 'none',
        boxShadow: 'none'
      } : {})
    }
  }), icon, children);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/Card.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Asgard surface card — the standard panel container. Optional `title`
 * renders the uppercase label + tinted icon chip used across the terminal.
 */
function Card({
  title,
  icon,
  accent = 'blue',
  action = null,
  children,
  style = {},
  ...rest
}) {
  const chip = {
    blue: {
      background: 'var(--blue-bg)',
      color: 'var(--blue)'
    },
    purple: {
      background: 'var(--pu-bg)',
      color: 'var(--pu)'
    },
    green: {
      background: 'var(--gr-bg)',
      color: 'var(--gr)'
    },
    red: {
      background: 'var(--re-bg)',
      color: 'var(--re)'
    },
    gold: {
      background: 'var(--gold-bg)',
      color: 'var(--gold)'
    }
  }[accent] || {
    background: 'var(--blue-bg)',
    color: 'var(--blue)'
  };
  return /*#__PURE__*/React.createElement("div", _extends({}, rest, {
    style: {
      background: 'var(--s1)',
      border: '1px solid var(--bd)',
      borderRadius: 'var(--r)',
      padding: '16px 18px',
      ...style
    }
  }), title && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      marginBottom: 13
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 7,
      fontSize: 10.5,
      fontWeight: 700,
      color: 'var(--t2)',
      textTransform: 'uppercase',
      letterSpacing: '0.07em',
      fontFamily: 'var(--font-sans)'
    }
  }, icon && /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: 24,
      height: 24,
      borderRadius: 'var(--rs)',
      flexShrink: 0,
      ...chip
    }
  }, icon), title), action), children);
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Card.jsx", error: String((e && e.message) || e) }); }

// components/forms/Input.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Asgard form input. Mono font, dark nested surface, blue focus border.
 * Pass `label` for the uppercase micro-label above the field.
 */
function Input({
  label,
  style = {},
  ...rest
}) {
  const [focus, setFocus] = React.useState(false);
  const field = /*#__PURE__*/React.createElement("input", _extends({}, rest, {
    onFocus: e => {
      setFocus(true);
      rest.onFocus?.(e);
    },
    onBlur: e => {
      setFocus(false);
      rest.onBlur?.(e);
    },
    style: {
      width: '100%',
      background: 'var(--s2)',
      border: `1px solid ${focus ? 'var(--blue-bd)' : 'var(--bd)'}`,
      borderRadius: 'var(--rs)',
      padding: '8px 11px',
      fontFamily: 'var(--font-mono)',
      fontSize: 13,
      color: 'var(--t1)',
      outline: 'none',
      transition: 'border-color var(--dur-base)',
      ...style
    }
  }));
  if (!label) return field;
  return /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'block'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'block',
      fontFamily: 'var(--font-sans)',
      fontSize: 9,
      fontWeight: 600,
      color: 'var(--t3)',
      textTransform: 'uppercase',
      letterSpacing: '0.08em',
      marginBottom: 4
    }
  }, label), field);
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Input.jsx", error: String((e && e.message) || e) }); }

// components/forms/Toggle.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Asgard toggle switch — green when on. Matches the Settings panel control.
 */
function Toggle({
  checked = false,
  onChange,
  disabled = false,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("label", {
    style: {
      position: 'relative',
      width: 42,
      height: 22,
      flexShrink: 0,
      display: 'inline-block',
      cursor: disabled ? 'default' : 'pointer',
      opacity: disabled ? 0.5 : 1
    }
  }, /*#__PURE__*/React.createElement("input", _extends({
    type: "checkbox",
    checked: checked,
    disabled: disabled,
    onChange: e => onChange?.(e.target.checked),
    style: {
      opacity: 0,
      width: 0,
      height: 0
    }
  }, rest)), /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'absolute',
      inset: 0,
      background: checked ? 'var(--gr)' : 'var(--s3)',
      borderRadius: 'var(--rp)',
      transition: 'background 0.2s'
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'absolute',
      width: 16,
      height: 16,
      borderRadius: '50%',
      background: '#fff',
      top: 3,
      left: 3,
      transform: checked ? 'translateX(20px)' : 'translateX(0)',
      transition: 'transform 0.2s',
      boxShadow: '0 1px 4px rgba(0,0,0,0.4)'
    }
  }));
}
Object.assign(__ds_scope, { Toggle });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Toggle.jsx", error: String((e && e.message) || e) }); }

// components/navigation/NavPills.jsx
try { (() => {
/**
 * Asgard nav pills — the rounded segmented navigation from the header.
 * Active pill is solid blue with a glow.
 */
function NavPills({
  items = [],
  value,
  onChange,
  style = {}
}) {
  return /*#__PURE__*/React.createElement("nav", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 4,
      padding: 5,
      background: 'var(--s2)',
      border: '1px solid var(--bd)',
      borderRadius: 'var(--rp)',
      ...style
    }
  }, items.map(item => {
    const id = typeof item === 'string' ? item : item.id;
    const label = typeof item === 'string' ? item : item.label;
    const icon = typeof item === 'string' ? null : item.icon;
    return /*#__PURE__*/React.createElement(Pill, {
      key: id,
      id: id,
      label: label,
      icon: icon,
      active: value === id,
      onClick: () => onChange?.(id)
    });
  }));
}
function Pill({
  id,
  label,
  icon,
  active,
  onClick
}) {
  const [hover, setHover] = React.useState(false);
  return /*#__PURE__*/React.createElement("button", {
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '9px 18px',
      fontFamily: 'var(--font-sans)',
      fontSize: 14,
      fontWeight: 600,
      lineHeight: 1,
      borderRadius: 'var(--rp)',
      border: 'none',
      cursor: 'pointer',
      transition: 'color var(--dur-base) var(--ease)',
      outline: 'none',
      background: active ? 'var(--blue)' : hover ? 'var(--s3)' : 'transparent',
      color: active ? '#fff' : hover ? 'var(--t1)' : 'var(--t2)',
      boxShadow: active ? 'var(--glow-blue)' : 'none'
    }
  }, icon, /*#__PURE__*/React.createElement("span", null, label));
}
Object.assign(__ds_scope, { NavPills });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/NavPills.jsx", error: String((e && e.message) || e) }); }

// components/trading/KpiStat.jsx
try { (() => {
const COLORS = {
  blue: 'var(--blue)',
  purple: 'var(--pu)',
  green: 'var(--gr)',
  red: 'var(--re)',
  gold: 'var(--gold)'
};

/**
 * Asgard KPI stat tile — uppercase label, large mono value, sublabel.
 * Used in the Stats KPI grid.
 */
function KpiStat({
  label,
  value,
  sub,
  accent = 'blue',
  style = {}
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--s1)',
      border: '1px solid var(--bd)',
      borderRadius: 'var(--r)',
      padding: '15px 17px',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 9,
      fontWeight: 600,
      color: 'var(--t3)',
      textTransform: 'uppercase',
      letterSpacing: '0.08em',
      marginBottom: 8
    }
  }, label), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 21,
      fontWeight: 700,
      color: COLORS[accent] || 'var(--blue)'
    }
  }, value), sub && /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 11,
      color: 'var(--t2)',
      marginTop: 5
    }
  }, sub));
}
Object.assign(__ds_scope, { KpiStat });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/trading/KpiStat.jsx", error: String((e && e.message) || e) }); }

// components/trading/SignalCard.jsx
try { (() => {
/**
 * Asgard AI signal card — purple left-accent, BUY/SELL direction tag,
 * confidence %, gradient confidence bar, and the model's reason quote.
 */
function SignalCard({
  base,
  quote = 'USDT',
  direction = 'BUY',
  confidence = 0,
  reason,
  onClick,
  style = {}
}) {
  const [hover, setHover] = React.useState(false);
  const isBuy = direction === 'BUY';
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      background: hover ? 'var(--s3)' : 'var(--s2)',
      border: `1px solid ${hover ? 'var(--pu-bd)' : 'var(--bd)'}`,
      borderLeft: '3px solid var(--pu)',
      borderRadius: 'var(--rs)',
      padding: '11px 13px',
      cursor: onClick ? 'pointer' : 'default',
      transition: 'all var(--dur-base)',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
      marginBottom: 7
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 13,
      fontWeight: 700,
      color: 'var(--t1)'
    }
  }, base, /*#__PURE__*/React.createElement("small", {
    style: {
      fontSize: 9.5,
      color: 'var(--t3)'
    }
  }, "/", quote)), /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-block',
      marginTop: 6,
      fontSize: 9.5,
      fontWeight: 700,
      padding: '2px 8px',
      borderRadius: 'var(--rp)',
      textTransform: 'uppercase',
      fontFamily: 'var(--font-sans)',
      background: isBuy ? 'var(--gr-bg)' : 'var(--re-bg)',
      color: isBuy ? 'var(--gr)' : 'var(--re)',
      border: `1px solid ${isBuy ? 'var(--gr-bd)' : 'var(--re-bd)'}`
    }
  }, direction)), /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: 'right'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 15,
      fontWeight: 700,
      color: 'var(--pu)'
    }
  }, confidence, "%"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 9,
      color: 'var(--t3)',
      fontWeight: 600,
      textTransform: 'uppercase'
    }
  }, "Confidence"))), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 2,
      background: 'var(--s1)',
      borderRadius: 2,
      marginBottom: 7
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: '100%',
      borderRadius: 2,
      width: `${confidence}%`,
      background: 'linear-gradient(90deg, var(--pu), var(--blue))'
    }
  })), reason && /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 11,
      color: 'var(--t2)',
      lineHeight: 1.55
    }
  }, "\"", reason, "\""));
}
Object.assign(__ds_scope, { SignalCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/trading/SignalCard.jsx", error: String((e && e.message) || e) }); }

// components/trading/Ticker.jsx
try { (() => {
/**
 * Asgard ticker tile — asset symbol, % change pill, mono price, H/L.
 * Active tiles get a blue left-accent. Used in the Trade ticker grid.
 */
function Ticker({
  base,
  quote = 'USDT',
  price,
  changePercent = 0,
  high,
  low,
  active = false,
  onClick,
  style = {}
}) {
  const [hover, setHover] = React.useState(false);
  const up = changePercent >= 0;
  return /*#__PURE__*/React.createElement("button", {
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      textAlign: 'left',
      width: '100%',
      padding: '13px 15px',
      cursor: 'pointer',
      background: active ? 'var(--blue-bg)' : hover ? 'var(--s2)' : 'var(--s1)',
      border: `1px solid ${active ? 'var(--blue-bd)' : hover ? 'var(--bd-h)' : 'var(--bd)'}`,
      borderLeft: `3px solid ${active ? 'var(--blue)' : 'transparent'}`,
      borderRadius: 'var(--r)',
      transition: 'all var(--dur-base)',
      outline: 'none',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: 9
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 13,
      fontWeight: 700,
      color: 'var(--t1)'
    }
  }, base, /*#__PURE__*/React.createElement("small", {
    style: {
      fontSize: 9.5,
      fontWeight: 500,
      color: 'var(--t3)'
    }
  }, "/", quote)), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10.5,
      fontWeight: 600,
      padding: '2px 8px',
      borderRadius: 'var(--rp)',
      fontFamily: 'var(--font-sans)',
      background: up ? 'var(--gr-bg)' : 'var(--re-bg)',
      color: up ? 'var(--gr)' : 'var(--re)'
    }
  }, up ? '▲' : '▼', " ", Math.abs(changePercent).toFixed(2), "%")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 17,
      fontWeight: 600,
      color: 'var(--t1)'
    }
  }, price), (high || low) && /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 9.5,
      fontWeight: 600,
      color: 'var(--t3)',
      marginTop: 4
    }
  }, "H: ", high, " L: ", low));
}
Object.assign(__ds_scope, { Ticker });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/trading/Ticker.jsx", error: String((e && e.message) || e) }); }

// ui_kits/terminal/Screens.jsx
try { (() => {
// Asgard Terminal — UI kit screens. Composes the design-system components
// (window.AsgardDesignSystem_d84b02) over mock data (window.ASGARD_DATA).
const DS = window.AsgardDesignSystem_d84b02;
const {
  Button,
  Card,
  Badge,
  Input,
  Toggle,
  Ticker,
  KpiStat,
  SignalCard,
  NavPills
} = DS;

// ── lucide icon helper ──
function Icon({
  name,
  size = 14,
  color = 'currentColor'
}) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    if (ref.current && window.lucide && window.lucide[name]) {
      ref.current.innerHTML = '';
      const el = window.lucide.createElement(window.lucide[name]);
      el.setAttribute('width', size);
      el.setAttribute('height', size);
      el.setAttribute('stroke', color);
      ref.current.appendChild(el);
    }
  }, [name, size, color]);
  return /*#__PURE__*/React.createElement("span", {
    ref: ref,
    style: {
      display: 'inline-flex'
    }
  });
}
const fmtPrice = p => p > 999 ? '$' + p.toLocaleString('en', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
}) : p.toFixed(4);
const fmtHL = p => p > 999 ? '$' + Math.round(p).toLocaleString('en') : p.toFixed(4);

// ───────────────────────── Header ─────────────────────────
function Header({
  tab,
  setTab,
  onLogout,
  portfolio
}) {
  const [menu, setMenu] = React.useState(false);
  const items = [{
    id: 'Trade',
    label: 'Trade',
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "TrendingUp",
      size: 15
    })
  }, {
    id: 'Stats',
    label: 'Stats',
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "BarChart3",
      size: 15
    })
  }, {
    id: 'Activity',
    label: 'Activity',
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "Activity",
      size: 15
    })
  }, {
    id: 'Settings',
    label: 'Settings',
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "Settings",
      size: 15
    })
  }];
  return /*#__PURE__*/React.createElement("header", {
    style: {
      height: 58,
      flexShrink: 0,
      background: 'var(--s1)',
      borderBottom: '1px solid var(--bd)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 22px',
      gap: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 9,
      minWidth: 136,
      cursor: 'pointer'
    },
    onClick: () => setTab('Trade')
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/asgard-logo.png",
    alt: "Asgard",
    style: {
      width: 28,
      height: 28,
      objectFit: 'contain'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      lineHeight: 1.05
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 15,
      fontWeight: 800,
      color: 'var(--gold)',
      letterSpacing: '0.1em',
      textTransform: 'uppercase'
    }
  }, "Asgard"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 8,
      fontWeight: 600,
      color: 'var(--t3)',
      letterSpacing: '0.2em',
      textTransform: 'uppercase'
    }
  }, "Intelligence"))), /*#__PURE__*/React.createElement(NavPills, {
    items: items,
    value: tab,
    onChange: setTab
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'flex-end',
      gap: 12,
      minWidth: 136
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 5,
      fontSize: 10,
      fontWeight: 600,
      color: 'var(--t2)',
      textTransform: 'uppercase',
      letterSpacing: '0.05em'
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "ldot"
  }), " Live"), /*#__PURE__*/React.createElement("div", {
    style: {
      width: 1,
      height: 26,
      background: 'var(--bd)'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'flex-end',
      gap: 1
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 8.5,
      fontWeight: 600,
      color: 'var(--t3)',
      textTransform: 'uppercase',
      letterSpacing: '0.07em'
    }
  }, "Total Equity"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 13,
      fontWeight: 600,
      color: 'var(--t1)'
    }
  }, "$", portfolio.equity.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative'
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: () => setMenu(!menu),
    style: {
      width: 32,
      height: 32,
      borderRadius: '50%',
      overflow: 'hidden',
      border: `2px solid ${menu ? 'var(--blue)' : 'var(--bd)'}`,
      cursor: 'pointer',
      background: 'var(--s2)',
      padding: 0
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/avatar-odin.svg",
    alt: "User",
    style: {
      width: '100%',
      height: '100%'
    }
  })), menu && /*#__PURE__*/React.createElement("div", {
    className: "animate-slide-up",
    style: {
      position: 'absolute',
      right: 0,
      marginTop: 12,
      width: 200,
      background: 'var(--s2)',
      border: '1px solid var(--bd)',
      borderRadius: 'var(--r)',
      boxShadow: 'var(--elev-3)',
      overflow: 'hidden',
      zIndex: 100
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 16,
      borderBottom: '1px solid var(--bd)',
      textAlign: 'center',
      background: 'var(--s1)'
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/avatar-odin.svg",
    alt: "",
    style: {
      width: 48,
      height: 48,
      borderRadius: '50%',
      border: '2px solid var(--blue)'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      fontWeight: 700,
      color: 'var(--t1)',
      marginTop: 6
    }
  }, "odin_trader"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: 'var(--gold)',
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '0.1em'
    }
  }, "Admin")), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 8
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: () => {
      setMenu(false);
      onLogout();
    },
    style: {
      width: '100%',
      textAlign: 'left',
      padding: '9px 11px',
      fontSize: 12,
      fontWeight: 600,
      color: 'var(--re)',
      background: 'none',
      border: 'none',
      borderRadius: 'var(--rs)',
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      gap: 9
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "LogOut",
    size: 14
  }), " Sign Out")))))));
}

// ───────────────────────── Login ─────────────────────────
function LoginScreen({
  onLogin
}) {
  const [u, setU] = React.useState('odin_trader');
  const [p, setP] = React.useState('••••••••');
  const [busy, setBusy] = React.useState(false);
  const submit = e => {
    e.preventDefault();
    setBusy(true);
    setTimeout(onLogin, 650);
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      height: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--bg)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: '100%',
      maxWidth: 360,
      padding: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: 'center',
      marginBottom: 28
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/asgard-logo.png",
    alt: "Asgard",
    style: {
      width: 64,
      height: 64,
      objectFit: 'contain',
      marginBottom: 12
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 22,
      fontWeight: 900,
      color: 'var(--t1)',
      letterSpacing: '-0.01em'
    }
  }, "ASGARD ", /*#__PURE__*/React.createElement("em", {
    style: {
      fontStyle: 'normal',
      color: 'var(--blue)'
    }
  }, "TRADING")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--t3)',
      marginTop: 4,
      textTransform: 'uppercase',
      letterSpacing: '0.12em'
    }
  }, "Algorithmic Execution Platform")), /*#__PURE__*/React.createElement(Card, {
    title: "Sign In",
    accent: "blue"
  }, /*#__PURE__*/React.createElement("form", {
    onSubmit: submit,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(Input, {
    label: "Username",
    value: u,
    onChange: e => setU(e.target.value)
  }), /*#__PURE__*/React.createElement(Input, {
    label: "Password",
    type: "password",
    value: p,
    onChange: e => setP(e.target.value)
  }), /*#__PURE__*/React.createElement(Button, {
    variant: "primary",
    type: "submit",
    disabled: busy,
    style: {
      width: '100%',
      marginTop: 4
    }
  }, busy ? 'Signing in…' : 'Sign In')))));
}

// ───────────────────────── Price chart (SVG) ─────────────────────────
function PriceChart({
  series
}) {
  const W = 900,
    H = 240,
    pL = 8,
    pR = 52,
    pT = 18,
    pB = 28;
  const cW = W - pL - pR,
    cH = H - pT - pB;
  const min = Math.min(...series) * 0.9998,
    max = Math.max(...series) * 1.0002,
    range = max - min || 1;
  const pts = series.map((v, i) => ({
    x: pL + i / (series.length - 1) * cW,
    y: pT + (1 - (v - min) / range) * cH
  }));
  const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
  const area = `${line} L ${pts[pts.length - 1].x.toFixed(1)} ${pT + cH} L ${pts[0].x.toFixed(1)} ${pT + cH} Z`;
  const lastY = pts[pts.length - 1].y;
  const yLabels = Array.from({
    length: 5
  }).map((_, i) => {
    const frac = i / 4,
      yp = pT + frac * cH,
      pv = max - frac * range;
    return {
      yp,
      label: '$' + (pv / 1000).toFixed(1) + 'k'
    };
  });
  return /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 900 240",
    preserveAspectRatio: "none",
    style: {
      width: '100%',
      display: 'block',
      overflow: 'visible'
    }
  }, /*#__PURE__*/React.createElement("defs", null, /*#__PURE__*/React.createElement("linearGradient", {
    id: "cg",
    x1: "0",
    y1: "0",
    x2: "0",
    y2: "1"
  }, /*#__PURE__*/React.createElement("stop", {
    offset: "0%",
    stopColor: "#4B9DFF",
    stopOpacity: "0.16"
  }), /*#__PURE__*/React.createElement("stop", {
    offset: "85%",
    stopColor: "#4B9DFF",
    stopOpacity: "0"
  }))), [1, 2, 3].map(i => {
    const yp = pT + i / 4 * cH;
    return /*#__PURE__*/React.createElement("line", {
      key: i,
      x1: pL,
      y1: yp,
      x2: W - pR,
      y2: yp,
      stroke: "rgba(255,255,255,0.04)"
    });
  }), /*#__PURE__*/React.createElement("path", {
    d: area,
    fill: "url(#cg)"
  }), /*#__PURE__*/React.createElement("path", {
    d: line,
    fill: "none",
    stroke: "#4B9DFF",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("line", {
    x1: pL,
    y1: lastY,
    x2: W - pR,
    y2: lastY,
    stroke: "#22C55E",
    strokeWidth: "1",
    strokeDasharray: "5,4",
    opacity: "0.45"
  }), /*#__PURE__*/React.createElement("g", {
    fontSize: "9",
    fill: "#445060",
    fontFamily: "JetBrains Mono, monospace"
  }, yLabels.map((l, i) => /*#__PURE__*/React.createElement("text", {
    key: i,
    x: W - pR + 4,
    y: l.yp + 3
  }, l.label))));
}
window.ASGARD_KIT = {
  Header,
  LoginScreen,
  PriceChart,
  Icon,
  fmtPrice,
  fmtHL
};
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/terminal/Screens.jsx", error: String((e && e.message) || e) }); }

// ui_kits/terminal/Views.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
// Asgard Terminal — main views (Trade / Stats / Activity).
const DSV = window.AsgardDesignSystem_d84b02;
const KIT = window.ASGARD_KIT;
const D = window.ASGARD_DATA;
function ViewHead({
  title,
  em,
  sub
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 16
    },
    className: "animate-slide-up"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 20,
      fontWeight: 700,
      letterSpacing: '-0.01em',
      color: 'var(--t1)'
    }
  }, title, " ", /*#__PURE__*/React.createElement("em", {
    style: {
      fontStyle: 'normal',
      color: 'var(--blue)'
    }
  }, em)), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11.5,
      color: 'var(--t2)',
      marginTop: 3
    }
  }, sub));
}

// ───────────────────────── Trade ─────────────────────────
function TradeView() {
  const {
    Card,
    Badge,
    Input,
    Ticker,
    SignalCard,
    Button
  } = DSV;
  const {
    PriceChart,
    Icon,
    fmtPrice,
    fmtHL
  } = KIT;
  const [sym, setSym] = React.useState('BTCUSDT');
  const [side, setSide] = React.useState('BUY');
  const [tf, setTf] = React.useState('1D');
  const [qty, setQty] = React.useState('0.1');
  const sel = D.tickers.find(t => t.symbol === sym) || D.tickers[0];
  const up = sel.changePercent >= 0;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      height: '100%',
      overflowY: 'auto',
      padding: '18px 22px'
    },
    className: "custom-scrollbar"
  }, /*#__PURE__*/React.createElement(ViewHead, {
    title: "System",
    em: "Intelligence",
    sub: "AI-powered market analysis \u2014 monitoring global assets with sub-second precision."
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: 9,
      marginBottom: 13
    }
  }, D.tickers.map(t => /*#__PURE__*/React.createElement(Ticker, {
    key: t.symbol,
    base: t.base,
    quote: t.quote,
    price: fmtPrice(t.price),
    changePercent: t.changePercent,
    high: fmtHL(t.high),
    low: fmtHL(t.low),
    active: t.symbol === sym,
    onClick: () => setSym(t.symbol)
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 350px',
      gap: 12,
      alignItems: 'start'
    }
  }, /*#__PURE__*/React.createElement(Card, {
    style: {
      padding: '16px 18px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 14,
      fontWeight: 700,
      color: 'var(--t1)'
    }
  }, sym, " ", /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11,
      color: 'var(--t2)',
      fontWeight: 500,
      marginLeft: 4
    }
  }, "Market Sentiment")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      gap: 8,
      marginTop: 3
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 22,
      fontWeight: 700,
      color: up ? 'var(--gr)' : 'var(--re)'
    }
  }, fmtPrice(sel.price)), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12,
      fontWeight: 600,
      color: up ? 'var(--gr)' : 'var(--re)'
    }
  }, up ? '▲' : '▼', " ", Math.abs(sel.changePercent).toFixed(2), "%"))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 2,
      padding: 3,
      background: 'var(--s2)',
      border: '1px solid var(--bd)',
      borderRadius: 'var(--rs)'
    }
  }, ['1H', '1D', '1W'].map(t => /*#__PURE__*/React.createElement("button", {
    key: t,
    onClick: () => setTf(t),
    style: {
      padding: '4px 11px',
      fontSize: 11,
      fontWeight: 600,
      borderRadius: 5,
      border: 'none',
      cursor: 'pointer',
      background: tf === t ? 'var(--blue)' : 'transparent',
      color: tf === t ? '#fff' : 'var(--t2)'
    }
  }, t)))), /*#__PURE__*/React.createElement(PriceChart, {
    series: D.chart
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(Card, {
    title: "Manual Trade",
    accent: "blue",
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "Wallet",
      size: 12
    })
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 3,
      padding: 3,
      background: 'var(--s2)',
      border: '1px solid var(--bd)',
      borderRadius: 'var(--rp)',
      marginBottom: 13
    }
  }, ['BUY', 'SELL'].map(s => /*#__PURE__*/React.createElement("button", {
    key: s,
    onClick: () => setSide(s),
    style: {
      flex: 1,
      padding: '8px 0',
      fontSize: 12,
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '0.05em',
      borderRadius: 'var(--rp)',
      border: 'none',
      cursor: 'pointer',
      background: side === s ? s === 'BUY' ? 'var(--gr)' : 'var(--re)' : 'transparent',
      color: side === s ? '#fff' : 'var(--t2)',
      boxShadow: side === s ? s === 'BUY' ? 'var(--glow-gr)' : 'var(--glow-re)' : 'none'
    }
  }, s))), /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 10
    }
  }, /*#__PURE__*/React.createElement(Input, {
    label: `Order Size (${sel.base})`,
    type: "number",
    value: qty,
    onChange: e => setQty(e.target.value)
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: 8,
      marginBottom: 10
    }
  }, /*#__PURE__*/React.createElement(Input, {
    label: "Stop Loss ($)",
    placeholder: "None"
  }), /*#__PURE__*/React.createElement(Input, {
    label: "Take Profit ($)",
    placeholder: "None"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--s2)',
      border: '1px solid var(--bd)',
      borderRadius: 'var(--rs)',
      padding: '8px 12px',
      marginBottom: 13
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      fontSize: 12,
      padding: '3px 0'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--t2)'
    }
  }, "Order Cost"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontWeight: 600,
      color: 'var(--blue)',
      fontSize: 14
    }
  }, "$", (sel.price * (parseFloat(qty) || 0)).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })))), /*#__PURE__*/React.createElement(Button, {
    variant: side === 'BUY' ? 'buy' : 'sell',
    icon: /*#__PURE__*/React.createElement("span", null, "\u2192"),
    style: {
      width: '100%'
    }
  }, "Execute ", side)), /*#__PURE__*/React.createElement(Card, {
    title: "AI Signals",
    accent: "purple",
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "Cpu",
      size: 12
    }),
    action: /*#__PURE__*/React.createElement(Badge, {
      tone: "purple",
      dot: true
    }, "Live")
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
      maxHeight: 320,
      overflowY: 'auto'
    },
    className: "custom-scrollbar"
  }, D.signals.map(s => /*#__PURE__*/React.createElement(SignalCard, {
    key: s.id,
    base: s.base,
    quote: s.quote,
    direction: s.direction,
    confidence: s.confidence,
    reason: s.reason,
    onClick: () => setSym(s.symbol)
  })))))));
}

// ───────────────────────── Stats ─────────────────────────
function StatsView() {
  const {
    Card,
    KpiStat
  } = DSV;
  const {
    Icon
  } = KIT;
  const max = Math.max(...D.agents.map(a => Math.abs(a.pnl)), 1);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      height: '100%',
      overflowY: 'auto',
      padding: '18px 22px'
    },
    className: "custom-scrollbar"
  }, /*#__PURE__*/React.createElement(ViewHead, {
    title: "Performance",
    em: "Stats",
    sub: "Historical equity curves, win rates, and per-agent contribution."
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: 9,
      marginBottom: 13
    }
  }, D.kpis.map(k => /*#__PURE__*/React.createElement(KpiStat, _extends({
    key: k.label
  }, k)))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 290px',
      gap: 12,
      alignItems: 'start'
    }
  }, /*#__PURE__*/React.createElement(Card, {
    title: "Comparative Backtest \u2014 30D (BTCUSDT)",
    accent: "blue",
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "Activity",
      size: 12
    })
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 14,
      marginBottom: 12,
      fontSize: 11,
      color: 'var(--t2)'
    }
  }, D.agents.map(a => /*#__PURE__*/React.createElement("span", {
    key: a.key,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 5
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 18,
      height: 2,
      borderRadius: 2,
      background: a.color
    }
  }), a.name))), /*#__PURE__*/React.createElement(StatsChart, null)), /*#__PURE__*/React.createElement(Card, {
    title: "Agent Breakdown",
    accent: "green",
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "Calendar",
      size: 12
    })
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 8
    }
  }, D.agents.map(a => /*#__PURE__*/React.createElement("div", {
    key: a.key,
    style: {
      background: 'var(--s2)',
      border: '1px solid var(--bd)',
      borderRadius: 'var(--rs)',
      padding: '11px 14px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      marginBottom: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12,
      fontWeight: 700,
      color: a.color
    }
  }, a.name), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 13,
      fontWeight: 700,
      color: a.pnl >= 0 ? 'var(--gr)' : 'var(--re)'
    }
  }, a.pnl >= 0 ? '+' : '', "$", a.pnl.toFixed(2))), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 3,
      background: 'var(--s1)',
      borderRadius: 2,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: '100%',
      borderRadius: 2,
      width: `${Math.abs(a.pnl) / max * 100}%`,
      background: a.color
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9.5,
      color: 'var(--t3)',
      marginTop: 4
    }
  }, "Win rate ", a.winrate, "% \xB7 ", a.trades, " trades")))))));
}
function StatsChart() {
  const W = 600,
    H = 180,
    pad = 12;
  const series = {
    loki: '#4B9DFF',
    thor: '#9B72FF',
    odin: '#F0A500'
  };
  const gen = seed => {
    const a = [];
    let v = 0;
    for (let i = 0; i < 30; i++) {
      v += (Math.random() - 0.4 + seed) * 8;
      a.push(v);
    }
    return a;
  };
  const data = {
    loki: gen(0.25),
    thor: gen(0.15),
    odin: gen(0.08)
  };
  const all = [].concat(...Object.values(data));
  const mn = Math.min(...all) - 4,
    mx = Math.max(...all) + 4,
    rng = mx - mn || 1;
  const path = arr => arr.map((v, i) => `${i === 0 ? 'M' : 'L'} ${(pad + i / (arr.length - 1) * (W - pad * 2)).toFixed(1)} ${(pad + (1 - (v - mn) / rng) * (H - pad * 2)).toFixed(1)}`).join(' ');
  return /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 600 180",
    preserveAspectRatio: "none",
    style: {
      width: '100%',
      display: 'block'
    }
  }, [45, 90, 135].map(y => /*#__PURE__*/React.createElement("line", {
    key: y,
    x1: "0",
    y1: y,
    x2: "600",
    y2: y,
    stroke: "rgba(255,255,255,0.04)"
  })), Object.entries(series).map(([k, c]) => /*#__PURE__*/React.createElement("path", {
    key: k,
    d: path(data[k]),
    fill: "none",
    stroke: c,
    strokeWidth: "2",
    strokeLinecap: "round"
  })));
}

// ───────────────────────── Activity ─────────────────────────
function ActivityView() {
  const {
    Card,
    Badge
  } = DSV;
  const {
    Icon
  } = KIT;
  const AGENT_COLOR = {
    LOKI: 'var(--blue)',
    THOR: 'var(--pu)',
    ODIN: 'var(--gold)',
    MANUAL: 'var(--t2)'
  };
  const th = {
    fontSize: 9,
    fontWeight: 600,
    color: 'var(--t3)',
    textTransform: 'uppercase',
    letterSpacing: '0.07em',
    padding: '0 0 9px',
    textAlign: 'left',
    borderBottom: '1px solid var(--bd)'
  };
  const td = {
    padding: '11px 0',
    fontSize: 12,
    borderBottom: '1px solid var(--bd)',
    fontFamily: 'var(--font-mono)',
    color: 'var(--t1)'
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      height: '100%',
      overflowY: 'auto',
      padding: '18px 22px'
    },
    className: "custom-scrollbar"
  }, /*#__PURE__*/React.createElement(ViewHead, {
    title: "Live",
    em: "Activity",
    sub: "Currently open positions and real-time trade logs."
  }), /*#__PURE__*/React.createElement(Card, {
    title: "Completed Trade History",
    accent: "blue",
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "FileText",
      size: 12
    })
  }, /*#__PURE__*/React.createElement("table", {
    style: {
      width: '100%',
      borderCollapse: 'collapse'
    }
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
    style: th
  }, "Time"), /*#__PURE__*/React.createElement("th", {
    style: th
  }, "Asset"), /*#__PURE__*/React.createElement("th", {
    style: th
  }, "Side"), /*#__PURE__*/React.createElement("th", {
    style: th
  }, "Agent"), /*#__PURE__*/React.createElement("th", {
    style: th
  }, "Entry"), /*#__PURE__*/React.createElement("th", {
    style: th
  }, "Close"), /*#__PURE__*/React.createElement("th", {
    style: {
      ...th,
      textAlign: 'right'
    }
  }, "Net PnL"))), /*#__PURE__*/React.createElement("tbody", null, D.history.map((h, i) => {
    const win = h.pnl >= 0;
    return /*#__PURE__*/React.createElement("tr", {
      key: i
    }, /*#__PURE__*/React.createElement("td", {
      style: {
        ...td,
        color: 'var(--t2)',
        fontSize: 10
      }
    }, h.time), /*#__PURE__*/React.createElement("td", {
      style: {
        ...td,
        fontFamily: 'var(--font-sans)',
        fontWeight: 700
      }
    }, h.base, /*#__PURE__*/React.createElement("small", {
      style: {
        color: 'var(--t3)'
      }
    }, "/", h.quote)), /*#__PURE__*/React.createElement("td", {
      style: td
    }, /*#__PURE__*/React.createElement(Badge, {
      tone: h.side === 'BUY' ? 'green' : 'red',
      bordered: false
    }, h.side)), /*#__PURE__*/React.createElement("td", {
      style: {
        ...td,
        fontFamily: 'var(--font-sans)',
        fontSize: 10,
        fontWeight: 700,
        color: AGENT_COLOR[h.agent]
      }
    }, h.agent), /*#__PURE__*/React.createElement("td", {
      style: td
    }, h.entry > 999 ? '$' + h.entry.toLocaleString() : h.entry), /*#__PURE__*/React.createElement("td", {
      style: td
    }, h.close > 999 ? '$' + h.close.toLocaleString() : h.close), /*#__PURE__*/React.createElement("td", {
      style: {
        ...td,
        textAlign: 'right',
        fontWeight: 700,
        color: win ? 'var(--gr)' : 'var(--re)'
      }
    }, win ? '+' : '−', "$", Math.abs(h.pnl).toFixed(2)));
  })))));
}

// ───────────────────────── Settings ─────────────────────────
function SettingsView() {
  const {
    Card,
    Toggle,
    Button
  } = DSV;
  const {
    Icon
  } = KIT;
  const [auto, setAuto] = React.useState(true);
  const [live, setLive] = React.useState(false);
  const [active, setActive] = React.useState('loki');
  const row = (title, desc, val, set) => /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '12px 14px',
      background: 'var(--s2)',
      border: '1px solid var(--bd)',
      borderRadius: 'var(--rs)',
      marginBottom: 9
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      fontWeight: 600,
      color: 'var(--t1)'
    }
  }, title), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--t2)',
      marginTop: 2
    }
  }, desc)), /*#__PURE__*/React.createElement(Toggle, {
    checked: val,
    onChange: set
  }));
  return /*#__PURE__*/React.createElement("div", {
    style: {
      height: '100%',
      overflowY: 'auto',
      padding: '18px 22px'
    },
    className: "custom-scrollbar"
  }, /*#__PURE__*/React.createElement(ViewHead, {
    title: "System",
    em: "Settings",
    sub: "Strategy, broker connections, safety controls, and API keys."
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 320px',
      gap: 12,
      alignItems: 'start'
    }
  }, /*#__PURE__*/React.createElement(Card, {
    title: "Active Strategy",
    accent: "blue",
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "Clock",
      size: 12
    })
  }, /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 11,
      color: 'var(--t2)',
      lineHeight: 1.6,
      marginTop: 0,
      marginBottom: 12
    }
  }, "One strategy trades live at a time. The other two are still evaluated for comparison."), D.agents.map(a => {
    const on = active === a.key;
    return /*#__PURE__*/React.createElement("button", {
      key: a.key,
      onClick: () => setActive(a.key),
      style: {
        width: '100%',
        textAlign: 'left',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '12px 15px',
        marginBottom: 8,
        borderRadius: 'var(--rs)',
        cursor: 'pointer',
        border: `1px solid ${on ? 'var(--bd-h)' : 'var(--bd)'}`,
        background: on ? 'var(--s2)' : 'transparent',
        boxShadow: on ? `inset 3px 0 0 ${a.color}` : 'none'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 12,
        height: 12,
        borderRadius: '50%',
        background: on ? a.color : 'var(--s3)'
      }
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        flex: 1
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        display: 'block',
        fontSize: 12.5,
        fontWeight: 700,
        color: a.color
      }
    }, a.name), /*#__PURE__*/React.createElement("span", {
      style: {
        display: 'block',
        fontSize: 10,
        color: 'var(--t3)'
      }
    }, a.key === 'loki' ? 'Quant Signals — pure math, AI trends & patterns' : a.key === 'thor' ? 'Balanced Blend — every signal source weighted equally' : 'Self-Learning — reinforcement-learning engine')), on && /*#__PURE__*/React.createElement(Icon, {
      name: "Check",
      size: 14,
      color: a.color
    }));
  }), /*#__PURE__*/React.createElement(Button, {
    variant: "primary",
    style: {
      width: '100%',
      marginTop: 4
    }
  }, "Save Configuration")), /*#__PURE__*/React.createElement(Card, {
    title: "Safety Controls",
    accent: "green",
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "Shield",
      size: 12
    })
  }, row('System Auto Mode', "Trades fire automatically on qualifying signals.", auto, setAuto), row('Live Mode', live ? 'LIVE — real orders on your broker' : 'Paper trading — no real orders', live, setLive), live && /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 10,
      color: 'var(--gold)',
      lineHeight: 1.5,
      marginTop: 8
    }
  }, "Live mode is active. Orders will be placed on your connected broker using real funds."))));
}
window.ASGARD_VIEWS = {
  TradeView,
  StatsView,
  ActivityView,
  SettingsView
};
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/terminal/Views.jsx", error: String((e && e.message) || e) }); }

// ui_kits/terminal/data.js
try { (() => {
// Mock market + portfolio data for the Asgard terminal UI kit.
window.ASGARD_DATA = {
  tickers: [{
    symbol: 'BTCUSDT',
    base: 'BTC',
    quote: 'USDT',
    price: 67482.10,
    changePercent: 2.41,
    high: 68120,
    low: 66540
  }, {
    symbol: 'ETHUSDT',
    base: 'ETH',
    quote: 'USDT',
    price: 3512.40,
    changePercent: -1.08,
    high: 3640,
    low: 3480
  }, {
    symbol: 'XAUUSD',
    base: 'XAU',
    quote: 'USD',
    price: 2356.80,
    changePercent: 0.62,
    high: 2371,
    low: 2342
  }, {
    symbol: 'EURUSD',
    base: 'EUR',
    quote: 'USD',
    price: 1.0842,
    changePercent: -0.18,
    high: 1.0871,
    low: 1.0829
  }],
  signals: [{
    id: 1,
    symbol: 'BTCUSDT',
    base: 'BTC',
    quote: 'USDT',
    direction: 'BUY',
    confidence: 82,
    reason: 'Momentum breakout confirmed by rising volume and bullish MACD cross.'
  }, {
    id: 2,
    symbol: 'XAUUSD',
    base: 'XAU',
    quote: 'USD',
    direction: 'SELL',
    confidence: 67,
    reason: 'Overbought RSI with bearish divergence on the 4H timeframe.'
  }, {
    id: 3,
    symbol: 'ETHUSDT',
    base: 'ETH',
    quote: 'USDT',
    direction: 'BUY',
    confidence: 74,
    reason: 'Reclaimed key support; correlation with BTC strengthening.'
  }, {
    id: 4,
    symbol: 'EURUSD',
    base: 'EUR',
    quote: 'USD',
    direction: 'SELL',
    confidence: 58,
    reason: 'Dollar strength ahead of CPI; range resistance holding.'
  }],
  kpis: [{
    label: 'Total Profit (Daily)',
    value: '+$1,204.50',
    sub: '+1.21% equity growth',
    accent: 'green'
  }, {
    label: 'Avg Win Rate',
    value: '61.4%',
    sub: 'Across active agents',
    accent: 'blue'
  }, {
    label: 'Profit Factor',
    value: '1.84×',
    sub: 'High efficiency zone',
    accent: 'purple'
  }, {
    label: 'Max Drawdown',
    value: '−4.20%',
    sub: 'Below risk ceiling',
    accent: 'red'
  }],
  agents: [{
    key: 'loki',
    name: 'Loki',
    pnl: 642.10,
    winrate: 64,
    trades: 38,
    color: 'var(--blue)'
  }, {
    key: 'thor',
    name: 'Thor',
    pnl: 388.40,
    winrate: 59,
    trades: 27,
    color: 'var(--pu)'
  }, {
    key: 'odin',
    name: 'Odin',
    pnl: 174.00,
    winrate: 57,
    trades: 19,
    color: 'var(--gold)'
  }],
  history: [{
    time: 'Jun 24, 14:02',
    base: 'BTC',
    quote: 'USDT',
    side: 'BUY',
    agent: 'LOKI',
    entry: 66980,
    close: 67410,
    pnl: 430.00
  }, {
    time: 'Jun 24, 11:48',
    base: 'ETH',
    quote: 'USDT',
    side: 'SELL',
    agent: 'THOR',
    entry: 3548,
    close: 3585,
    pnl: -37.00
  }, {
    time: 'Jun 24, 09:15',
    base: 'XAU',
    quote: 'USD',
    side: 'BUY',
    agent: 'ODIN',
    entry: 2341,
    close: 2356,
    pnl: 150.00
  }, {
    time: 'Jun 23, 22:30',
    base: 'EUR',
    quote: 'USD',
    side: 'SELL',
    agent: 'LOKI',
    entry: 1.0871,
    close: 1.0842,
    pnl: 29.00
  }, {
    time: 'Jun 23, 18:04',
    base: 'BTC',
    quote: 'USDT',
    side: 'BUY',
    agent: 'MANUAL',
    entry: 66500,
    close: 66120,
    pnl: -380.00
  }],
  portfolio: {
    equity: 11204.50,
    balance: 8420.30
  },
  // a soft random-walk price series for the chart
  chart: (() => {
    const pts = [];
    let v = 66000;
    for (let i = 0; i < 60; i++) {
      v += Math.sin(i / 4) * 120 + (Math.random() - 0.45) * 180;
      pts.push(v);
    }
    return pts;
  })()
};
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/terminal/data.js", error: String((e && e.message) || e) }); }

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.Input = __ds_scope.Input;

__ds_ns.Toggle = __ds_scope.Toggle;

__ds_ns.NavPills = __ds_scope.NavPills;

__ds_ns.KpiStat = __ds_scope.KpiStat;

__ds_ns.SignalCard = __ds_scope.SignalCard;

__ds_ns.Ticker = __ds_scope.Ticker;

})();
