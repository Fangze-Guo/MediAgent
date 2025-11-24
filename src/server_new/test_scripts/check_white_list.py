from pathlib import Path
from mediagent.modules.tm_test import TaskManager  # 按你真实路径改

def main():
    # === 这里按你当前工程实际配置填 ===
    PUBLIC_ROOT = Path(r"D:\projects\MediAgent2\src\server_new\data\files\public")  # 你 public datasets 的根
    WORKSPACE_ROOT = Path(r"D:\projects\MediAgent2\src\server_new\data\processed") # 你 workspace 根
    DB_FILE = Path(r"D:\projects\MediAgent2\src\server_new\data\db\mediagent.db")  # 你的 sqlite
    MCP_SERVER = Path(r"D:\projects\MediAgent2\src\server_new\mediagent\mcp_server_tools\mcp_server.py")

    tm = TaskManager(
        public_datasets_source_root=PUBLIC_ROOT,
        workspace_root=WORKSPACE_ROOT,
        database_file=DB_FILE,
        mcpserver_file=MCP_SERVER,
    )

    print("\n=== tools_index (WHITE LIST) ===")
    print(sorted(tm.tools_index.keys()))

    print("\n=== allowed_tool_names ===")
    print(sorted(tm.allowed_tool_names))

    print("\n=== all_tools_index (ALL MCP TOOLS) ===")
    print(sorted(tm.all_tools_index.keys()))

    # 判一下走的哪条路径
    if any(name.startswith("start_") or name.startswith("train_") for name in tm.tools_index):
        print("\n[HINT] tools_index seems valid.")
    if "train_hiomics_pipeline" not in tm.tools_index:
        print("\n[WARNING] train_hiomics_pipeline NOT in whitelist!")

    tm.close()

if __name__ == "__main__":
    main()
