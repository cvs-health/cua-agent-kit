#!/bin/sh
# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

set -eu

if [ "${DATABASE_BACKEND:-none}" = "postgres" ]; then
    export FLYWAY_URL="${DATABASE_JDBC_URI:?Set DATABASE_JDBC_URI}"
    export FLYWAY_USER="${DATABASE_USER:?Set DATABASE_USER}"
    flyway migrate
fi

exec "$@"
