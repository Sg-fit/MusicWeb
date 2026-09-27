// Fresh Feed — play + like interactions (no framework, plain fetch).

document.addEventListener("click", async (e) => {
  // ----- Play: load the embed inline and log a play -----
  const playBtn = e.target.closest(".play-btn");
  if (playBtn) {
    const player = playBtn.closest(".player");
    const card = playBtn.closest(".card");
    const id = card.dataset.id;
    const kind = player.dataset.kind;
    const embed = player.dataset.embed;
    const url = player.dataset.url;

    player.innerHTML = renderPlayer(kind, embed, url);

    try {
      const r = await fetch(`/play/${id}`, { method: "POST" });
      const data = await r.json();
      const pc = card.querySelector(".play-count");
      if (pc) pc.textContent = data.plays;
    } catch (_) { /* non-fatal */ }
    return;
  }

  // ----- Like: toggle -----
  const likeBtn = e.target.closest(".like-btn");
  if (likeBtn) {
    const id = likeBtn.dataset.id;
    try {
      const r = await fetch(`/like/${id}`, { method: "POST" });
      const data = await r.json();
      likeBtn.classList.toggle("liked", data.liked);
      likeBtn.querySelector(".heart").textContent = data.liked ? "♥" : "♡";
      likeBtn.querySelector(".like-count").textContent = data.likes;
    } catch (_) { /* non-fatal */ }
    return;
  }
});

function renderPlayer(kind, embed, url) {
  if (kind === "youtube" || kind === "soundcloud") {
    return `<iframe class="frame" src="${embed}" frameborder="0"
              allow="autoplay; encrypted-media" allowfullscreen loading="lazy"></iframe>`;
  }
  if (kind === "audio") {
    return `<audio class="audio" controls autoplay src="${embed}"></audio>`;
  }
  return `<a class="ext" href="${url}" target="_blank" rel="noopener">Open track in new tab ↗</a>`;
}
