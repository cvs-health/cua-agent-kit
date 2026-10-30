/*
 * SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
 * SPDX-License-Identifier: Apache-2.0
 */

"use strict";

const el = (id) => document.getElementById(id);
let referrals = null;
let selected;

function show(id) {
  for (const name of ["login", "inventory", "checkout", "confirmation"]) {
    el(name).hidden = name !== id;
  }
}

async function loadReferrals() {
  if (referrals !== null) return;
  const response = await fetch("data.json");
  if (!response.ok) throw new Error("Could not load referral data");
  const data = await response.json();
  referrals = data.referrals;
}

function render(query = "") {
  el("products").replaceChildren();
  const matches = referrals.filter((referral) =>
    (referral.id + " " + referral.name).toLowerCase().includes(query.toLowerCase())
  );

  for (const referral of matches) {
    const article = document.createElement("article");
    const heading = document.createElement("h2");
    heading.textContent = referral.id + " — " + referral.name;
    const specialty = document.createElement("p");
    specialty.textContent = referral.specialty + " · Ready to schedule";
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Schedule " + referral.id;
    button.addEventListener("click", () => {
      selected = referral;
      el("selected").textContent =
        referral.id + " — " + referral.name + " — " + referral.specialty;
      show("checkout");
    });
    article.append(heading, specialty, button);
    el("products").append(article);
  }

  if (matches.length === 0) {
    const message = document.createElement("p");
    message.textContent = "No referrals found.";
    el("products").append(message);
  }
}

el("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  el("error").textContent = "";
  if (el("username").value !== "demo" || el("password").value !== "demo-password") {
    el("error").textContent = "Incorrect demo credentials";
    return;
  }

  const button = event.submitter;
  if (button) button.disabled = true;
  try {
    await loadReferrals();
    el("password").value = "";
    render();
    show("inventory");
  } catch {
    el("error").textContent = "Could not load referrals. Please try signing in again.";
  } finally {
    if (button) button.disabled = false;
  }
});

el("search-form").addEventListener("submit", (event) => {
  event.preventDefault();
  render(el("search").value);
});

el("order-form").addEventListener("submit", (event) => {
  event.preventDefault();
  el("summary").textContent =
    selected.id + " — " + selected.name + " — " + selected.specialty +
    " — " + el("quantity").value + " at " + el("customer").value + " — Scheduled";
  show("confirmation");
});

el("reset").addEventListener("click", () => location.reload());
