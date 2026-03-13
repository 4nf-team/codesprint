chrome.action.onClicked.addListener(() => {
  chrome.windows.create({
    url: "popup.html",
    type: "popup", // Тип "popup" убирает лишние панели браузера (вкладки, адресную строку)
    width: 380,
    height: 600
  });
});