请根据用户修改意图和当前 YAML，生成可验证的 patch operations。

每个 operation 必须包含 type、target_path、reason 和 payload。reason 必须使用中文，payload 必须只包含必要改动。

