#!/bin/bash
# Protection wrapper for supabase init - requires permission

supabase() {
    if [ "$1" = "init" ]; then
        echo "🛡️  SUPABASE INIT PROTECTION"
        echo "You are about to create a new Supabase instance in: $(pwd)"
        echo ""
        echo "Existing Supabase projects:"
        docker volume ls --filter "label=com.supabase.cli.project" --format "{{.Labels}}" | grep -o "project=[^,]*" | sort -u
        echo ""
        read -p "Type 'YES' to proceed: " confirm
        if [ "$confirm" != "YES" ]; then
            echo "❌ Cancelled"
            return 1
        fi
    fi
    command supabase "$@"
}
