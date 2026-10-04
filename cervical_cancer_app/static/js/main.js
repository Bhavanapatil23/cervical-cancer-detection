// Toggle smokes years field
function toggleSmokes() {
  const val = document.getElementById("smokesSelect").value;
  const wrap = document.getElementById("smokesYearsWrap");
  const def  = document.getElementById("smokesYearsDefault");
  if (val === "1") {
    wrap.style.display = "flex";
    wrap.querySelector("input").required = true;
    def.disabled = true;
  } else {
    wrap.style.display = "none";
    wrap.querySelector("input").required = false;
    wrap.querySelector("input").value = "";
    def.disabled = false;
    def.value = "0";
  }
}

// Toggle STDs number + HPV fields
function toggleSTDs() {
  const val = document.getElementById("stdsSelect").value;
  const numWrap = document.getElementById("stdsNumberWrap");
  const hpvWrap = document.getElementById("stdsHpvWrap");
  const numDef  = document.getElementById("stdsNumberDefault");
  const hpvDef  = document.getElementById("stdsHpvDefault");

  if (val === "1") {
    numWrap.style.display = "flex";
    hpvWrap.style.display = "flex";
    numWrap.querySelector("input").required = true;
    numDef.disabled = true;
    hpvDef.disabled = true;
  } else {
    numWrap.style.display = "none";
    hpvWrap.style.display = "none";
    numWrap.querySelector("input").required = false;
    numWrap.querySelector("input").value = "";
    numDef.disabled = false;
    numDef.value = "0";
    hpvDef.disabled = false;
    hpvDef.value = "0";
  }
}

// Loading state on submit
document.getElementById("riskForm")?.addEventListener("submit", function () {
  const btn = this.querySelector(".submit-btn");
  btn.innerHTML = `<span>Analyzing...</span>
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
         style="animation:spin 1s linear infinite">
      <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
    </svg>`;
  btn.disabled = true;
});

// CSS for spin
const style = document.createElement("style");
style.textContent = `@keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }`;
document.head.appendChild(style);