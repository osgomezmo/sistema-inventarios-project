const admin = require('firebase-admin');

let estaConfigurado = false;
let db = null;
let messaging = null;

const storageDriver = process.env.STORAGE_DRIVER || 'local';
const pushDriver = process.env.PUSH_DRIVER || 'console';
const necesitaFirebase = storageDriver === 'firestore' || pushDriver === 'fcm';

if (necesitaFirebase) {
  try {
    const projectId = process.env.FIREBASE_PROJECT_ID;
    const clientEmail = process.env.FIREBASE_CLIENT_EMAIL;
    let privateKey = process.env.FIREBASE_PRIVATE_KEY;

    if (privateKey) {
      privateKey = privateKey.replace(/\\n/g, '\n');
    }

    if (projectId && clientEmail && privateKey) {
      if (!admin.apps.length) {
        admin.initializeApp({
          credential: admin.credential.cert({
            projectId,
            clientEmail,
            privateKey,
          }),
        });
      }
      estaConfigurado = true;
      db = admin.firestore();
      messaging = admin.messaging();
    } else if (process.env.GOOGLE_APPLICATION_CREDENTIALS) {
      if (!admin.apps.length) {
        admin.initializeApp({
          credential: admin.credential.applicationDefault(),
        });
      }
      estaConfigurado = true;
      db = admin.firestore();
      messaging = admin.messaging();
    } else {
      console.warn(
        '[FIREBASE] Se solicitó un driver que requiere Firebase (firestore o fcm) pero faltan credenciales. Firebase permanece inactivo.'
      );
    }
  } catch (error) {
    console.error('[FIREBASE] Error al inicializar firebase-admin:', error.message);
  }
}

module.exports = {
  admin: estaConfigurado ? admin : null,
  db,
  messaging,
  estaConfigurado,
};
