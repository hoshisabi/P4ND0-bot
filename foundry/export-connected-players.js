/**
 * Foundry VTT script macro: export connected players and their characters.
 *
 * Setup:
 * 1. Macro Directory → Create Macro
 * 2. Type: Script
 * 3. Paste this entire file into the Command field
 * 4. Run while players are connected (GM only)
 *
 * Output: downloads a JSON file and copies the same payload to your clipboard.
 */

const INCLUDE_GMS = false;
const INCLUDE_UNASSIGNED_PLAYERS = true;

function getConnectedPlayers() {
  return game.users.filter((user) => {
    if (!user.active) return false;
    if (!INCLUDE_GMS && user.isGM) return false;
    return true;
  });
}

function getCharactersForUser(user) {
  const characters = new Map();

  if (user.character) {
    characters.set(user.character.id, user.character);
  }

  for (const actor of game.actors) {
    if (actor.type !== "character") continue;
    if (characters.has(actor.id)) continue;
    if (actor.testUserPermission(user, "OWNER")) {
      characters.set(actor.id, actor);
    }
  }

  return [...characters.values()];
}

function getRace(actor) {
  const details = actor.system?.details;
  const race = details?.race;

  if (race instanceof Item) return race.name;
  if (typeof race === "object" && race?.name) return race.name;
  if (typeof race === "string" && race.trim()) return race;

  const species =
    actor.itemTypes?.race?.[0] ??
    actor.itemTypes?.species?.[0] ??
    actor.items?.find((item) => item.type === "race" || item.type === "species");

  return species?.name ?? null;
}

function getClassEntries(actor) {
  if (actor.classes && Object.keys(actor.classes).length > 0) {
    return Object.values(actor.classes).map((cls) => ({
      name: cls.name,
      level: cls.system?.levels ?? null,
    }));
  }

  const legacy = actor.system?.classes;
  if (legacy && typeof legacy === "object") {
    return Object.entries(legacy).map(([key, data]) => ({
      name: data?.name ?? key,
      level: data?.levels ?? data?.level ?? null,
    }));
  }

  return [];
}

function getTotalLevel(actor, classEntries) {
  if (Number.isFinite(actor.system?.details?.level)) {
    return actor.system.details.level;
  }

  return classEntries.reduce((sum, cls) => sum + (Number(cls.level) || 0), 0) || null;
}

function formatClasses(classEntries) {
  if (!classEntries.length) return null;
  return classEntries.map((cls) => `${cls.name} ${cls.level ?? "?"}`).join(" / ");
}

const DDB_CHARACTER_ID_RE = /(?:dndbeyond\.com\/characters\/|\/characters\/)(\d+)/i;

function extractDdbCharacterId(value) {
  if (value == null || value === "") return null;
  if (typeof value === "number") return String(value);

  const text = String(value).trim();
  const match = text.match(DDB_CHARACTER_ID_RE);
  if (match) return match[1];
  if (/^\d+$/.test(text)) return text;
  return null;
}

function getDndBeyondUrl(actor) {
  const flagSources = [
    actor.flags?.["ddb-importer"],
    actor.flags?.ddbimporter,
    actor.flags?.ddbImporter,
    actor.flags,
  ].filter(Boolean);

  for (const flags of flagSources) {
    const ddb = flags.dndBeyond ?? flags.dndbeyond ?? flags;
    const characterId = extractDdbCharacterId(
      ddb.characterId ?? ddb.id ?? flags.characterId ?? flags.ddbCharacterId
    );
    if (characterId) {
      return `https://www.dndbeyond.com/characters/${characterId}`;
    }

    for (const candidate of [ddb.url, ddb.characterUrl, flags.characterUrl, flags.url]) {
      const fromUrl = extractDdbCharacterId(candidate);
      if (fromUrl) return `https://www.dndbeyond.com/characters/${fromUrl}`;
    }
  }

  for (const candidate of [
    actor.img,
    actor.prototypeToken?.texture?.src,
    actor.system?.details?.biography?.value,
    actor.system?.details?.biography,
  ]) {
    const fromUrl = extractDdbCharacterId(candidate);
    if (fromUrl) return `https://www.dndbeyond.com/characters/${fromUrl}`;
  }

  return null;
}

function getAvatarUrl(actor) {
  return actor.img || actor.prototypeToken?.texture?.src || null;
}

function summarizeCharacter(actor) {
  const classEntries = getClassEntries(actor);

  return {
    name: actor.name,
    race: getRace(actor),
    level: getTotalLevel(actor, classEntries),
    classes: formatClasses(classEntries),
    dndBeyondUrl: getDndBeyondUrl(actor),
    avatarUrl: getAvatarUrl(actor),
  };
}

function summarizeUser(user) {
  return {
    id: user.id,
    name: user.name,
  };
}

function buildExportPayload() {
  const players = getConnectedPlayers();

  const payload = {
    exportedAt: new Date().toISOString(),
    world: game.world.title,
    worldId: game.world.id,
    system: game.system.id,
    connectedPlayerCount: players.length,
    players: [],
  };

  for (const user of players) {
    const characters = getCharactersForUser(user);

    if (!INCLUDE_UNASSIGNED_PLAYERS && characters.length === 0) {
      continue;
    }

    payload.players.push({
      user: summarizeUser(user),
      characters: characters.map(summarizeCharacter),
    });
  }

  return payload;
}

function filenameStamp(date = new Date()) {
  return date.toISOString().replace(/[:.]/g, "-").slice(0, 19);
}

async function copyText(text) {
  if (foundry.utils?.copyTextToClipboard) {
    await foundry.utils.copyTextToClipboard(text);
    return;
  }

  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  throw new Error("Clipboard API is not available in this browser context.");
}

function downloadJson(json, filename) {
  if (foundry.utils?.downloadData) {
    foundry.utils.downloadData(json, filename, "application/json");
    return;
  }

  const blob = new Blob([json], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

const payload = buildExportPayload();
const json = JSON.stringify(payload, null, 2);
const filename = `connected-players-${filenameStamp()}.json`;

console.log(`[Export Connected Players] ${payload.connectedPlayerCount} connected player(s):`, payload);

downloadJson(json, filename);

try {
  await copyText(json);
  ui.notifications.info(
    `Exported ${payload.players.length} connected player(s) to ${filename} and copied JSON to clipboard.`,
    { permanent: false }
  );
} catch (error) {
  console.warn("[Export Connected Players] Download succeeded but clipboard copy failed:", error);
  ui.notifications.warn(
    `Exported ${payload.players.length} connected player(s) to ${filename}. Clipboard copy failed — see downloaded file or browser console.`,
    { permanent: false }
  );
}
