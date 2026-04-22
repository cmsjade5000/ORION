import { describe, expect, it } from "vitest";

const { parseInitData, signInitData, validateInitData } = require("./auth.cjs");

describe("mini app auth", () => {
  it("parses and validates Telegram init data", () => {
    const botToken = "123456:ABCDEF";
    const authDate = Math.floor(Date.now() / 1000);
    const encodedUser = JSON.stringify({ id: 12345, first_name: "Cory", username: "corystoner" });
    const fields = {
      auth_date: String(authDate),
      query_id: "AAEAAAE",
      user: encodedUser,
    };
    const hash = signInitData(fields, botToken);
    const raw = new URLSearchParams({ ...fields, hash }).toString();

    const parsed = parseInitData(raw);
    expect(parsed.user).toMatchObject({ id: 12345, username: "corystoner" });

    const validated = validateInitData(raw, botToken, { maxAgeSeconds: 60 });
    expect(validated.ok).toBe(true);
    expect(validated.fields.user.id).toBe(12345);
  });

  it("validates against raw init data bytes instead of re-serialized JSON", () => {
    const botToken = "123456:ABCDEF";
    const authDate = Math.floor(Date.now() / 1000);
    const encodedUser =
      '{"id":12345,"first_name":"Cory","photo_url":"https:\\/\\/t.me\\/i\\/userpic\\/320\\/orion.jpg"}';
    const fields = {
      auth_date: String(authDate),
      query_id: "AAEAAAE",
      user: encodedUser,
    };
    const hash = signInitData(fields, botToken);
    const raw = new URLSearchParams({ ...fields, hash }).toString();

    const validated = validateInitData(raw, botToken, { maxAgeSeconds: 60 });
    expect(validated.ok).toBe(true);
    expect(validated.fields.user.photo_url).toBe("https://t.me/i/userpic/320/orion.jpg");
  });

  it("rejects expired payloads", () => {
    const botToken = "123456:ABCDEF";
    const fields = {
      auth_date: String(Math.floor(Date.now() / 1000) - 600),
      user: JSON.stringify({ id: 12345 }),
    };
    const hash = signInitData(fields, botToken);
    const raw = new URLSearchParams({ ...fields, hash }).toString();
    const validated = validateInitData(raw, botToken, { maxAgeSeconds: 30 });
    expect(validated.ok).toBe(false);
    expect(validated.reason).toBe("expired");
  });
});
