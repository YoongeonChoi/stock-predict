const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const rootDir = path.resolve(__dirname, "..");
const frontendDir = path.join(rootDir, "frontend");
const frontendPackage = path.join(frontendDir, "package.json");

if (!fs.existsSync(frontendPackage)) {
  console.error(`[fail] 프론트 package.json을 찾을 수 없습니다: ${frontendPackage}`);
  process.exit(1);
}

function run(args) {
  if (args.length === 0) {
    console.error("[fail] frontend npm 명령 인자가 비어 있습니다.");
    return 1;
  }

  const npmExecPath = process.env.npm_execpath;

  if (npmExecPath && fs.existsSync(npmExecPath)) {
    const completed = spawnSync(process.execPath, [npmExecPath, ...args], {
      cwd: frontendDir,
      stdio: "inherit",
    });
    return completed.status ?? 1;
  }

  const fallbackCommand = process.platform === "win32" ? "npm.cmd" : "npm";
  const completed = spawnSync(fallbackCommand, args, {
    cwd: frontendDir,
    stdio: "inherit",
  });

  if (typeof completed.status === "number") {
    return completed.status;
  }

  if (completed.error) {
    console.error(`[fail] 프론트 npm 명령 실행에 실패했습니다: ${completed.error.message}`);
  }
  return 1;
}

if (require.main === module) {
  process.exit(run(process.argv.slice(2)));
}

module.exports = { run };
