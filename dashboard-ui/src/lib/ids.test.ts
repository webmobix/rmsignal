import { describe, expect, it } from "vitest";
import { idKind } from "./ids";

describe("idKind", () => {
	it.each([
		["CL-0002", "client"],
		["PF-0001", "portfolio"],
		["SYN-AL-0301", "instrument"],
		["ev_7c47d71cd093e49f", "evidence"],
		["CL-0002#f17", "finding"],
	])("%s is %s", (id, kind) => expect(idKind(id)).toBe(kind));
});
