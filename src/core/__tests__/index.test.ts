import { loadWorkingMemory, workingMemory } from "../index";

describe("Core module working memory loader", () => {
  it("loadWorkingMemory returns the content of memory/WORKING.md", () => {
    const content = loadWorkingMemory();
    expect(content).toContain("# Working Memory");
  });

  it("workingMemory constant equals loadWorkingMemory()", () => {
    expect(workingMemory).toBe(loadWorkingMemory());
  });
});
