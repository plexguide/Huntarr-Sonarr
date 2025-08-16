<h2 align="center">Huntarr - Find Missing & Upgrade Media Items</h2> 

<p align="center">
  <img src="frontend/static/logo/128.png" alt="Huntarr Logo" width="100" height="100">
</p>

<a href="https://plexguide.github.io/Huntarr.io/donate.html">
  <img src="https://img.shields.io/github/sponsors/plexguide?style=flat&logo=github&logoColor=white&label=Support%20Huntarr&color=blue" alt="Support Huntarr" />
</a>

---

<h2 align="center">Want to Help? Click the Star in the Upper-Right Corner! ⭐</h2> 

<img src="https://github.com/user-attachments/assets/1ea6ca9c-0909-4b6a-b573-f778b65af8b2" width="100%"/>

#### ⭐ Show Your Support for Open Source!

If Huntarr has been helpful to you and you appreciate the power of open-source software, please consider giving this repository a star. Your gesture will greatly support our efforts and help others discover Huntarr!

<p align="center">
  <a href="https://github.com/plexguide/Huntarr.io/stargazers">
    <img src="https://reporoster.com/stars/dark/plexguide/Huntarr.io?max=6" alt="Stargazers repo roster for @plexguide/Huntarr.io" style="border: 1px solid #30363d; border-radius: 6px;" />
  </a>
</p>
 
<div align="center">

| **Sonarr** | **Radarr** | **Lidarr** | **Readarr** |
|:----------:|:----------:|:----------:|:-----------:|
| <img src="https://img.shields.io/badge/Status-Ready-green?style=flat" alt="Ready" /> | <img src="https://img.shields.io/badge/Status-Ready-green?style=flat" alt="Ready" /> | <img src="https://img.shields.io/badge/Status-Ready-green?style=flat" alt="Ready" /> | <img src="https://img.shields.io/badge/Status-Ready-green?style=flat" alt="Ready" /> |

| **Whisparr v2** | **Whisparr v3** | **Bazarr** |
|:---------------:|:---------------:|:----------:|
| <img src="https://img.shields.io/badge/Status-Ready-green?style=flat" alt="Ready" /> | <img src="https://img.shields.io/badge/Status-Ready-green?style=flat" alt="Ready" /> | <img src="https://img.shields.io/badge/Status-Not%20Ready-red?style=flat" alt="Not Ready" /> |

</div>

## Table of Contents
- [Overview](#overview)
- [Why You Need Huntarr](#why-you-need-huntarr)
- [Other Projects](#other-projects)
- [Indexers Approving of Huntarr](#indexers-approving-of-huntarr)
- [Installation Methods](#installation-methods)
- [How It Works](#how-it-works)
- [Thank You](#thank-you)
- [Screenshots](#screenshots)
- [The Perfect Pair: Huntarr & Cleanuparr](#the-perfect-pair-huntarr--cleanuparr)
- [Change Log](#change-log)

## ℹ️ Overview

[![Discord](https://img.shields.io/discord/1370922258247454821?color=7289DA&label=Discord&style=for-the-badge&logo=discord)](https://discord.com/invite/PGJJjR5Cww)

This application continually searches your media libraries for missing content and items that need quality upgrades. It automatically triggers searches for both missing items and those below your quality cutoff. It's designed to run continuously while being gentle on your indexers, helping you gradually complete your media collection with the best available quality.

For detailed documentation, please visit our <a href="https://plexguide.github.io/Huntarr.io/" target="_blank" rel="noopener noreferrer">Wiki</a>.

## ❓ Why You Need Huntarr

Huntarr is an automatic missing content hunter for Sonarr, Radarr, Lidarr, Readarr, and Whisparr.  
Think of it as the missing piece that actually completes your media automation setup by finding and downloading all the content your *arr apps aren't actively searching for.

**The problem**: Your *arr apps only monitor RSS feeds for new releases. They don't go back and search for missing episodes/movies already in your library. It's also a hard concept for many to understand the gap this creates.

**The solution**: Huntarr systematically scans your entire library, finds all missing content, and searches for it in small batches that won't overwhelm your indexers or get you banned. It's the difference between having a "mostly complete" library and actually having everything you want.

## 🔀 Other Projects

* [Unraid Intel ARC Deployment](https://github.com/plexguide/Unraid_Intel-ARC_Deployment) - Convert videos to AV1 Format (I've saved 325TB encoding to AV1)
* Visit [PlexGuide](https://plexguide.com) for more great scripts



## PayPal Donations – For My Daughter's College Fund

My 12-year-old daughter is passionate about singing, dancing, and exploring STEM. She consistently earns A-B honors! Every donation goes directly into her college fund!

[![Donate with PayPal button](https://www.paypalobjects.com/en_US/i/btn/btn_donate_LG.gif)](https://www.paypal.com/donate?hosted_button_id=58AYJ68VVMGSC)

## 👍 Indexers Approving of Huntarr:
* https://ninjacentral.co.za

## ⬇️ Installation Methods

- 🐋 **[Docker Installation](https://plexguide.github.io/Huntarr.io/getting-started/installation.html)**
- 🪟 **[Windows Installation](https://plexguide.github.io/Huntarr.io/getting-started/installation.html#windows-installation)**
- 🍏 **[macOS Installation](https://plexguide.github.io/Huntarr.io/getting-started/installation.html#macos-installation)**
- 🔵 **[Unraid Installation](https://plexguide.github.io/Huntarr.io/getting-started/installation.html#unraid-installation)**
- 🔧 **[Alternative Methods](https://plexguide.github.io/Huntarr.io/getting-started/installation.html#alternative-methods)**

Special thanks to [Nwithan8](https://github.com/nwithan8) for maintaining the Unraid templates and helping Huntarr grow through the Unraid Community Applications repository.

## ⚙️ How It Works

### 🔄 Continuous Automation Cycle

<i class="fas fa-1"></i> **Connect & Analyze** - Huntarr connects to your Sonarr/Radarr/Lidarr/Readarr/Whisparr/Eros instances and analyzes your media libraries to identify both missing content and potential quality upgrades.

<i class="fas fa-2"></i> **Hunt Missing Content** - Efficiently refreshes by skipping metadata to reduce disk I/O and database load, automatically skips content with future release dates, provides precise control over how many items to process per cycle, and focuses only on content you've marked as monitored.

<i class="fas fa-3"></i> **Hunt Quality Upgrades** - Finds content below your quality cutoff settings for improvement, uses batch processing to set specific numbers of upgrades per cycle, automatically pauses when download queue exceeds your threshold, and waits for commands to complete with consistent timeouts.

<i class="fas fa-4"></i> **API Management** - Implements hourly caps to prevent overloading your indexers, uses consistent API timeouts (120s) across all applications, identifies as Huntarr to all Arr applications with consistent headers, and provides visual indicators showing API usage limits.

<i class="fas fa-5"></i> **Repeat & Rest** - Huntarr waits for your configured interval (adjustable in settings) before starting the next cycle, ensuring your indexers aren't overloaded while maintaining continuous improvement of your library.

---

## ❤️ Thank You

A big thank you to these amazing contributors who've helped build and maintain this project:

<a href="https://github.com/plexguide/Huntarr.io/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=plexguide/Huntarr.io" alt="Contributors" />
</a>

## 📸 Screenshots

<p align="center">
  <img width="100%" alt="Homepage" src="https://github.com/user-attachments/assets/c060962c-01ee-4f53-a5ee-c67f31432e40" style="border: 1px solid #30363d; border-radius: 6px; margin-bottom: 10px;" />
</p>

<p align="center">
  <img width="100%" alt="Logger UI" src="https://github.com/user-attachments/assets/93c1a5d3-e82a-416a-8d41-0379ea221d7a" style="border: 1px solid #30363d; border-radius: 6px; margin-bottom: 10px;" />
</p>

<p align="center">
  <img width="930" alt="Settings UI" src="https://github.com/user-attachments/assets/e87867f8-0a8c-48d8-b6ef-234caa33e41f" style="border: 1px solid #30363d; border-radius: 6px;" />
</p>

---

## 🤝 The Perfect Pair: Huntarr & Cleanuparr

<p align="center">
  <img src="https://github.com/plexguide/Huntarr.io/blob/main/frontend/static/logo/128.png?raw=true" alt="Huntarr" width="64" height="64">
  <span style="font-size: 32px; margin: 0 15px;">+</span>
  <img src="https://github.com/cleanuparr/cleanuparr/blob/main/Logo/128.png?raw=true" alt="Cleanuparr" width="64" height="64">
</p>

**Huntarr** is the compulsive librarian who finds missing media and upgrades your existing content. It fills in the blanks and improves what you already have.

**Cleanuparr** ([![GitHub stars](https://img.shields.io/github/stars/cleanuparr/cleanuparr?style=social)](https://github.com/cleanuparr/cleanuparr/stargazers)) is the janitor of your server; it keeps your download queue spotless, removes clutter, and blocks malicious files.

When combined, these tools create a powerful, self-sufficient media automation stack:

- **Huntarr** hunts for content to add to your library
- **Cleanuparr** ensures only clean downloads get through
- Together, they create a reliable, hands-off media management system

Learn more about **Cleanuparr** at [https://github.com/cleanuparr/cleanuparr](https://github.com/cleanuparr/cleanuparr)

## 📜 Change Log
Visit: https://github.com/plexguide/Huntarr.io/releases/
