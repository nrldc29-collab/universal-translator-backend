# Mobile Guide

The mobile client is an Expo (React Native) app living in `translator-mobile/`.
It targets iOS, Android, and a web export for testing.

## Quick start

```bash
cd translator-mobile
npm install
npm start            # open the Expo dev server (QR for Expo Go)
npm run android      # launch on a connected Android device/emulator
npm run ios          # launch on a connected iOS device/simulator
npm run web          # browser export for quick UI iteration
npm run lint         # expo lint (ESLint + Expo rules)
npm run build       