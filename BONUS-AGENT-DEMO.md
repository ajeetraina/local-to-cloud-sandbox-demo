# Bonus: instructor demo with a real agent (15 min)

On stage, run the same flow with Claude Code working on the real [catalog-service-node](https://github.com/dockersamples/catalog-service-node) app. The app stays on your laptop; only the agent's work moves. This needs your own Anthropic key.

1. Set up and start locally, with the repo cloned inside the sandbox:

    ```
    sbx secret set -g anthropic
    sbx create --name catalog-agent claude
    sbx exec catalog-agent git clone https://github.com/dockersamples/catalog-service-node.git /home/agent/catalog
    sbx run --name catalog-agent
    ```

2. Give Claude the task:

    > In /home/agent/catalog, add a category column to the products table (dev/db/1-create-schema.sql) and a GET /api/products?category=<name> endpoint. Add unit tests. Do not start containers or run integration tests. Run npm run unit-test until it passes. Commit each working step on branch feature/category-search.

    The products table has no category column today, so the agent has to change the schema too. The unit tests run without containers.

3. Once the first commit lands, prepare the cloud side and move:

    ```
    echo "$ANTHROPIC_API_KEY" | sbx --cloud secret set anthropic
    sbx --cloud policy allow network "github.com,registry.npmjs.org"
    sbx move catalog-agent --to cloud --name catalog-agent --ttl 2h --on-timeout hibernate --force
    sbx --cloud ls
    ```

4. Attach and resume, using the name or ID from `sbx --cloud ls` (it keeps the `catalog-agent` name unless that name was already taken):

    ```
    sbx --cloud attach catalog-agent
    ```

    Tell Claude: "Continue the category search work. Check git log and run the unit tests to see where you left off." Detach with Ctrl-\.

5. Bring the work home and test it against the real app on your laptop:

    ```
    sbx --cloud exec catalog-agent git -C /home/agent/catalog format-patch main --stdout > category-search.patch
    git clone https://github.com/dockersamples/catalog-service-node.git
    cd catalog-service-node
    git am ../category-search.patch
    docker compose up -d
    npm install
    npm run integration-test
    ```

6. Clean up:

    ```
    sbx --cloud rm catalog-agent
    sbx rm catalog-agent
    ```

**The message for the room:** the sandbox is where the agent works safely, the cloud is where it keeps working while you're away, and your real stack stays on your machine where you review and test the result.
