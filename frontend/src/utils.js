/**
 * Shared utilities for the Anai Translator web client.
 *
 * Extracted from `main.jsx` so that file can focus on the App component.
 * Everything here is pure (no React) -- constants, browser feature probes,
 * latency/audio helpers, repair-label formatting, and small URL helpers.
 *
 * Side effects: `registerServiceWorker()` is *not* called here; callers
 * must invoke it. localStorage reads are wrapped in try/catch so the
 * module is safe to import in SSR-ish environments.
 */

// ---------- Host classification + default URLs ----------

export function isLocalHost(hostname) {
  return (
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname.startsWith('192.168.') ||
    hostname.startsWith('10.') ||
    /^172\.(1[6-9]|2\d|3[0-1])\./.test(hostname)
  );
}

export function isSameOriginBackendHost(hostname) {
  return (
    hostname.endsWith('.trycloudflare.com') ||
    hostname.endsWith('.up.railway.app') ||
    hostname.endsWith('.onrender.com') ||
    hostname.endsWith('.fly.dev')
  );
}

export function defaultApiUrl() {
  if (isLocalHost(window.location.hostname)) {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  if (isSameOriginBackendHost(window.location.hostname)) {
    return window.location.origin;
  }
  return '';
}

/** Treat `your-backend.example.com`-style placeholders as unset. */
export function configuredUrl(value) {
  if (!value || value.includes('your-backend')) return '';
  return value;
}

// ---------- Session/device identifiers ----------

export function normalizeSessionId(value) {
  return String(value || '').trim().replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 64);
}

export function readInitialSessionId() {
  const params = new URLSearchParams(window.location.search);
  const linkedSession = normalizeSessionId(params.get('session') || params.get('room'));
  return (
    linkedSession ||
    normalizeSessionId(localStorage.getItem('translator_session_id')) ||
    crypto.randomUUID()
  );
}

// ---------- Constants ----------

export const TARGET_LANGUAGE_OPTIONS = [
  { code: 'en', label: 'English', native: 'English', flag: '🇺🇸', dir: 'ltr', group: 'european', popularity: 1, family: 'Indo-European', speakers: '1.5B', difficulty: 1, script: 'Latin', currency: '$', ttsVoice: 'en-US-Neural2', units: 'imperial', keyboard: 'QWERTY', cultural: 'Direct communication, personal space valued', dateFormat: 'MDY', nameOrder: 'firstLast' },
  { code: 'es', label: 'Spanish', native: 'Español', flag: '🇪🇸', dir: 'ltr', group: 'european', popularity: 2, family: 'Indo-European', speakers: '550M', difficulty: 2, script: 'Latin', currency: '€', ttsVoice: 'es-ES-Neural2', units: 'metric', keyboard: 'QWERTY', cultural: 'Formal address with usted, close physical contact', dateFormat: 'DMY', nameOrder: 'firstLast' },
  { code: 'ht', label: 'Haitian Creole', native: 'Kreyòl Ayisyen', flag: '🇭🇹', dir: 'ltr', group: 'caribbean', popularity: 12, family: 'Creole', speakers: '12M', difficulty: 3, script: 'Latin', currency: 'HTG', ttsVoice: 'fr-HT-Standard', units: 'metric', keyboard: 'QWERTY', cultural: 'French-influenced, warm hospitality', dateFormat: 'DMY', nameOrder: 'firstLast' },
  { code: 'fr', label: 'French', native: 'Français', flag: '🇫🇷', dir: 'ltr', group: 'european', popularity: 5, family: 'Indo-European', speakers: '300M', difficulty: 3, script: 'Latin', currency: '€', ttsVoice: 'fr-FR-Neural2', units: 'metric', keyboard: 'AZERTY', cultural: 'Formal vous, appreciation of art and cuisine', dateFormat: 'DMY', nameOrder: 'firstLast', variants: ['fr-CA', 'fr-BE'] },
  { code: 'de', label: 'German', native: 'Deutsch', flag: '🇩🇪', dir: 'ltr', group: 'european', popularity: 6, family: 'Indo-European', speakers: '230M', difficulty: 4, script: 'Latin', currency: '€', ttsVoice: 'de-DE-Neural2', units: 'metric', keyboard: 'QWERTZ', cultural: 'Punctual, formal Sie, direct communication', dateFormat: 'DMY', nameOrder: 'firstLast', variants: ['de-AT', 'de-CH'] },
  { code: 'it', label: 'Italian', native: 'Italiano', flag: '🇮🇹', dir: 'ltr', group: 'european', popularity: 7, family: 'Indo-European', speakers: '70M', difficulty: 3, script: 'Latin', currency: '€', ttsVoice: 'it-IT-Neural2', units: 'metric', keyboard: 'QWERTY', cultural: 'Formal Lei, emphasis on family and food', dateFormat: 'DMY', nameOrder: 'firstLast', variants: ['it-CH'] },
  { code: 'pt', label: 'Portuguese', native: 'Português', flag: '🇧🇷', dir: 'ltr', group: 'european', popularity: 8, family: 'Indo-European', speakers: '260M', difficulty: 2, script: 'Latin', currency: 'R$', ttsVoice: 'pt-BR-Neural2', units: 'metric', keyboard: 'QWERTY', cultural: 'Warm, informal você, expressive gestures', dateFormat: 'DMY', nameOrder: 'firstLast', variants: ['pt-PT'] },
  { code: 'zh', label: 'Chinese', native: '中文', flag: '🇨🇳', dir: 'ltr', group: 'asian', popularity: 3, family: 'Sino-Tibetan', speakers: '1.1B', difficulty: 5, script: 'Hanzi', currency: '¥', ttsVoice: 'zh-CN-Neural2', units: 'metric', keyboard: 'Pinyin', cultural: 'Respect for hierarchy, indirect communication', dateFormat: 'YMD', nameOrder: 'lastFirst', variants: ['zh-TW', 'zh-HK'], font: 'system-ui, "PingFang SC", "Microsoft YaHei", sans-serif' },
  { code: 'ja', label: 'Japanese', native: '日本語', flag: '🇯🇵', dir: 'ltr', group: 'asian', popularity: 9, family: 'Japonic', speakers: '125M', difficulty: 5, script: 'Hiragana/Katakana/Kanji', currency: '¥', ttsVoice: 'ja-JP-Neural2', units: 'metric', keyboard: 'JIS', cultural: 'Polite keigo, group harmony, bowing', dateFormat: 'YMD', nameOrder: 'lastFirst', font: 'system-ui, "Hiragino Kaku Gothic Pro", "Yu Gothic", sans-serif' },
  { code: 'ko', label: 'Korean', native: '한국어', flag: '🇰🇷', dir: 'ltr', group: 'asian', popularity: 10, family: 'Koreanic', speakers: '80M', difficulty: 4, script: 'Hangul', currency: '₩', ttsVoice: 'ko-KR-Neural2', units: 'metric', keyboard: 'Hangul', cultural: 'Respect for age, honorifics, communal dining', dateFormat: 'YMD', nameOrder: 'lastFirst', font: 'system-ui, "Malgun Gothic", "Apple SD Gothic Neo", sans-serif' },
  { code: 'ar', label: 'Arabic', native: 'العربية', flag: '🇸🇦', dir: 'rtl', group: 'middle-eastern', popularity: 4, family: 'Semitic', speakers: '370M', difficulty: 5, script: 'Arabic', currency: '﷼', ttsVoice: 'ar-SA-Standard', units: 'metric', keyboard: 'Arabic', cultural: 'Hospitality, religious phrases, gender-specific forms', dateFormat: 'DMY', nameOrder: 'firstLast', variants: ['ar-EG', 'ar-MA'], font: 'system-ui, "Segoe UI", "Arial", sans-serif' },
  { code: 'ru', label: 'Russian', native: 'Русский', flag: '🇷🇺', dir: 'ltr', group: 'european', popularity: 11, family: 'Indo-European', speakers: '260M', difficulty: 4, script: 'Cyrillic', currency: '₽', ttsVoice: 'ru-RU-Neural2', units: 'metric', keyboard: 'JCUKEN', cultural: 'Formal vy, patronymics, direct expression', dateFormat: 'DMY', nameOrder: 'firstLast', font: 'system-ui, "Segoe UI", "Arial", sans-serif' },
];

export const VOICE_WARMUP_PHRASES = {
  es: {
    casual: ['Hola, ¿cómo estás?', '¿Qué tal?', 'Buenas'],
    formal: ['Buenos días', 'Buenas tardes', 'Buenas noches'],
    greeting: ['Hola', 'Saludos', 'Bienvenido'],
    farewell: ['Adiós', 'Hasta luego', 'Nos vemos'],
    thanks: ['Gracias', 'Muchas gracias', 'Te agradezco'],
    apology: ['Lo siento', 'Perdón', 'Disculpa'],
    question: ['¿Cómo estás?', '¿Qué pasa?', '¿De dónde eres?'],
    affirmation: ['Sí', 'Claro que sí', 'Por supuesto'],
    negation: ['No', 'No gracias', 'No lo sé'],
    introduction: ['Me llamo...', 'Soy de...', 'Mucho gusto'],
    numbers: ['Uno, dos, tres', 'Primero, segundo', 'Cien, mil'],
    time: ['Es la una', 'Son las tres', 'Mediodía', 'Medianoche'],
    directions: ['A la derecha', 'A la izquierda', 'Siga recto', 'Gire'],
    food: ['Está delicioso', 'Buen provecho', 'Tengo hambre', 'Tengo sed'],
    weather: ['Hace sol', 'Está lloviendo', 'Hace frío', 'Hace calor'],
    emergency: ['¡Ayuda!', '¡Socorro!', 'Llame a la policía', 'Necesito un médico'],
    colors: ['Rojo', 'Azul', 'Verde', 'Amarillo', 'Negro', 'Blanco'],
    animals: ['Perro', 'Gato', 'Pájaro', 'Pez', 'Caballo', 'Vaca'],
    transportation: ['Coche', 'Autobús', 'Tren', 'Avión', 'Barco', 'Bicicleta'],
    shopping: ['¿Cuánto cuesta?', 'Es muy caro', '¿Tiene cambio?', 'Quiero comprar'],
    family: ['Madre', 'Padre', 'Hermano', 'Hermana', 'Hijo', 'Hija'],
    work: ['Trabajo', 'Oficina', 'Reunión', 'Jefe', 'Compañero', 'Salario'],
    education: ['Escuela', 'Universidad', 'Profesor', 'Estudiante', 'Examen', 'Diploma'],
    health: ['Hospital', 'Doctor', 'Medicina', 'Enfermedad', 'Salud', 'Recuperación'],
  },
  ht: {
    casual: ['Bonjou, kijan ou ye?', 'Koman ou ye?', 'Sak pase?'],
    formal: ['Bonjou', 'Bonswa', 'Orevwa'],
    greeting: ['Bonjou', 'Alò', 'Sak pase?'],
    farewell: ['Orevwa', 'Na wè pita', 'Bye'],
    thanks: ['Mèsi', 'Mèsi anpil', 'Mèsi boukou'],
    apology: ['Eskize m', 'Padon', 'Mwen regrèt'],
    question: ['Kijan ou ye?', 'Kisa ki pase?', 'Ki kote ou soti?'],
    affirmation: ['Wi', 'Wi, menm', 'Sepa'],
    negation: ['Non', 'Non mèsi', 'Mwen pa konnen'],
    introduction: ['Mwen rele...', 'Mwen soti nan...', 'Plezi'],
    numbers: ['Youn, de, twa', 'Premye, dezyèm', 'San, mil'],
    time: ['Li yon èdtan', 'Li twa èdtan', 'Midi', 'Minwi'],
    directions: ['A dwat', 'A goch', 'Ale dwat', 'Vire'],
    food: ['Li bon', 'Bon apetit', 'Mwen grangou', 'Mwen swaf'],
    weather: ['Sol la leve', 'Li plouve', 'Li frèt', 'Li cho'],
    emergency: ['Èd m!', 'Sekou!', ' rele polis', 'Mwen bezwen yon doktè'],
    colors: ['Wouj', 'Ble', 'Vèt', 'Jòn', 'Nwa', 'Blan'],
    animals: ['Chen', 'Chat', 'Zwazo', 'Pwason', 'Cheval', 'Bèf'],
    transportation: [' machin', 'Kamyon', 'Tren', 'Avyon', 'Bato', 'Velosipèd'],
    shopping: ['Konbyen li koute?', 'Li chè anpil', 'Ou gen chanj?', 'Mwen vwen achte'],
    family: ['Manman', 'Papa', 'Frè', 'Sè', 'Fi', 'Pitit'],
    work: ['Travay', 'Biwo', 'Reyinyon', 'Patwòn', 'Kolèg', 'Salaire'],
    education: ['Lekòl', 'Inivèsite', 'Pwofesè', 'Etidyan', 'Egzamen', 'Diplòm'],
    health: ['Lopital', 'Doktè', 'Medikaman', 'Maladi', 'Sante', 'Rekipèrasyon'],
  },
  fr: {
    casual: ['Salut, ça va?', 'Coucou', 'Bonjour'],
    formal: ['Bonjour, comment allez-vous?', 'Bonsoir', 'Enchanté'],
    greeting: ['Bonjour', 'Salut', 'Bonsoir'],
    farewell: ['Au revoir', 'À bientôt', 'Adieu'],
    thanks: ['Merci', 'Merci beaucoup', 'Je vous remercie'],
    apology: ['Je suis désolé', 'Pardon', 'Excusez-moi'],
    question: ['Comment ça va?', 'Quoi de neuf?', 'D\'où venez-vous?'],
    affirmation: ['Oui', 'Bien sûr', 'Absolument'],
    negation: ['Non', 'Non merci', 'Je ne sais pas'],
    introduction: ['Je m\'appelle...', 'Je viens de...', 'Enchanté'],
    numbers: ['Un, deux, trois', 'Premier, deuxième', 'Cent, mille'],
    time: ['Il est une heure', 'Il est trois heures', 'Midi', 'Minuit'],
    directions: ['À droite', 'À gauche', 'Tout droit', 'Tournez'],
    food: ['C\'est délicieux', 'Bon appétit', 'J\'ai faim', 'J\'ai soif'],
    weather: ['Il fait beau', 'Il pleut', 'Il fait froid', 'Il fait chaud'],
    emergency: ['Au secours!', 'Aidez-moi!', 'Appelez la police', 'J\'ai besoin d\'un médecin'],
    colors: ['Rouge', 'Bleu', 'Vert', 'Jaune', 'Noir', 'Blanc'],
    animals: ['Chien', 'Chat', 'Oiseau', 'Poisson', 'Cheval', 'Vache'],
    transportation: ['Voiture', 'Bus', 'Train', 'Avion', 'Bateau', 'Vélo'],
    shopping: ['Combien ça coûte?', 'C\'est très cher', 'Vous avez la monnaie?', 'Je veux acheter'],
    family: ['Mère', 'Père', 'Frère', 'Sœur', 'Fils', 'Fille'],
    work: ['Travail', 'Bureau', 'Réunion', 'Patron', 'Collègue', 'Salaire'],
    education: ['École', 'Université', 'Professeur', 'Étudiant', 'Examen', 'Diplôme'],
    health: ['Hôpital', 'Médecin', 'Médecine', 'Maladie', 'Santé', 'Récupération'],
  },
  de: {
    casual: ['Hallo, wie geht\'s?', 'Na?', 'Hi'],
    formal: ['Guten Tag', 'Guten Morgen', 'Guten Abend'],
    greeting: ['Hallo', 'Guten Tag', 'Tschüss'],
    farewell: ['Auf Wiedersehen', 'Tschüss', 'Bis bald'],
    thanks: ['Danke', 'Vielen Dank', 'Danke schön'],
    apology: ['Es tut mir leid', 'Entschuldigung', 'Verzeihung'],
    question: ['Wie geht es dir?', 'Was gibt\'s Neues?', 'Woher kommst du?'],
    affirmation: ['Ja', 'Natürlich', 'Auf jeden Fall'],
    negation: ['Nein', 'Nein danke', 'Ich weiß nicht'],
    introduction: ['Ich heiße...', 'Ich komme aus...', 'Freut mich'],
    numbers: ['Eins, zwei, drei', 'Erster, zweiter', 'Hundert, tausend'],
    time: ['Es ist ein Uhr', 'Es ist drei Uhr', 'Mittag', 'Mitternacht'],
    directions: ['Rechts', 'Links', 'Geradeaus', 'Drehen'],
    food: ['Es ist lecker', 'Guten Appetit', 'Ich habe Hunger', 'Ich habe Durst'],
    weather: ['Die Sonne scheint', 'Es regnet', 'Es ist kalt', 'Es ist heiß'],
    emergency: ['Hilfe!', 'Rufen Sie die Polizei', 'Ich brauche einen Arzt'],
    colors: ['Rot', 'Blau', 'Grün', 'Gelb', 'Schwarz', 'Weiß'],
    animals: ['Hund', 'Katze', 'Vogel', 'Fisch', 'Pferd', 'Kuh'],
    transportation: ['Auto', 'Bus', 'Zug', 'Flugzeug', 'Schiff', 'Fahrrad'],
    shopping: ['Wie viel kostet das?', 'Das ist sehr teuer', 'Haben Sie Wechselgeld?', 'Ich möchte kaufen'],
    family: ['Mutter', 'Vater', 'Bruder', 'Schwester', 'Sohn', 'Tochter'],
    work: ['Arbeit', 'Büro', 'Besprechung', 'Chef', 'Kollege', 'Gehalt'],
    education: ['Schule', 'Universität', 'Professor', 'Student', 'Prüfung', 'Diplom'],
    health: ['Krankenhaus', 'Arzt', 'Medizin', 'Krankheit', 'Gesundheit', 'Genesung'],
  },
  it: {
    casual: ['Ciao, come stai?', 'Ehi', 'Pronto'],
    formal: ['Buongiorno', 'Buonasera', 'Piacere'],
    greeting: ['Ciao', 'Salve', 'Arrivederci'],
    farewell: ['Arrivederci', 'Addio', 'A presto'],
    thanks: ['Grazie', 'Grazie mille', 'Ti ringrazio'],
    apology: ['Mi dispiace', 'Scusa', 'Perdonami'],
    question: ['Come stai?', 'C\'è di nuovo?', 'Da dove vieni?'],
    affirmation: ['Sì', 'Certamente', 'Assolutamente'],
    negation: ['No', 'No grazie', 'Non lo so'],
    introduction: ['Mi chiamo...', 'Vengo da...', 'Piacere'],
    numbers: ['Uno, due, tre', 'Primo, secondo', 'Cento, mille'],
    time: ['È l\'una', 'Sono le tre', 'Mezzogiorno', 'Mezzanotte'],
    directions: ['A destra', 'A sinistra', 'Dritto', 'Gira'],
    food: ['È delizioso', 'Buon appetito', 'Ho fame', 'Ho sete'],
    weather: ['C\'è il sole', 'Piove', 'Fa freddo', 'Fa caldo'],
    emergency: ['Aiuto!', 'Chiami la polizia', 'Ho bisogno di un medico'],
    colors: ['Rosso', 'Blu', 'Verde', 'Giallo', 'Nero', 'Bianco'],
    animals: ['Cane', 'Gatto', 'Uccello', 'Pesce', 'Cavallo', 'Mucca'],
    transportation: ['Automobile', 'Autobus', 'Treno', 'Aereo', 'Nave', 'Bicicletta'],
    shopping: ['Quanto costa?', 'È molto costoso', 'Hai il resto?', 'Voglio comprare'],
    family: ['Madre', 'Padre', 'Fratello', 'Sorella', 'Figlio', 'Figlia'],
    work: ['Lavoro', 'Ufficio', 'Riunione', 'Capo', 'Collega', 'Stipendio'],
    education: ['Scuola', 'Università', 'Professore', 'Studente', 'Esame', 'Diploma'],
    health: ['Ospedale', 'Medico', 'Medicina', 'Malattia', 'Salute', 'Recupero'],
  },
  pt: {
    casual: ['Oi, tudo bem?', 'E aí?', 'Fala'],
    formal: ['Bom dia', 'Boa tarde', 'Boa noite'],
    greeting: ['Olá', 'Oi', 'Tudo bem?'],
    farewell: ['Tchau', 'Até logo', 'Adeus'],
    thanks: ['Obrigado', 'Muito obrigado', 'Valeu'],
    apology: ['Desculpe', 'Me desculpe', 'Sinto muito'],
    question: ['Como você está?', 'O que há de novo?', 'De onde você é?'],
    affirmation: ['Sim', 'Claro', 'Com certeza'],
    negation: ['Não', 'Não obrigado', 'Não sei'],
    introduction: ['Meu nome é...', 'Sou de...', 'Prazer'],
    numbers: ['Um, dois, três', 'Primeiro, segundo', 'Cem, mil'],
    time: ['É uma hora', 'São três horas', 'Meio-dia', 'Meia-noite'],
    directions: ['À direita', 'À esquerda', 'Em frente', 'Vire'],
    food: ['Está delicioso', 'Bom apetite', 'Estou com fome', 'Estou com sede'],
    weather: ['Está ensolarado', 'Está chovendo', 'Está frio', 'Está quente'],
    emergency: ['Socorro!', 'Ajuda!', 'Chame a polícia', 'Preciso de um médico'],
    colors: ['Vermelho', 'Azul', 'Verde', 'Amarelo', 'Preto', 'Branco'],
    animals: ['Cachorro', 'Gato', 'Pássaro', 'Peixe', 'Cavalo', 'Vaca'],
    transportation: ['Carro', 'Ônibus', 'Trem', 'Avião', 'Barco', 'Bicicleta'],
    shopping: ['Quanto custa?', 'É muito caro', 'Você tem troco?', 'Quero comprar'],
    family: ['Mãe', 'Pai', 'Irmão', 'Irmã', 'Filho', 'Filha'],
    work: ['Trabalho', 'Escritório', 'Reunião', 'Chefe', 'Colega', 'Salário'],
    education: ['Escola', 'Universidade', 'Professor', 'Estudante', 'Exame', 'Diploma'],
    health: ['Hospital', 'Médico', 'Medicina', 'Doença', 'Saúde', 'Recuperação'],
  },
  zh: {
    casual: ['你好，你好吗？', '嗨', '嘿'],
    formal: ['您好', '幸会', '请多关照'],
    greeting: ['你好', '您好', '早上好'],
    farewell: ['再见', '回头见', '拜拜'],
    thanks: ['谢谢', '非常感谢', '多谢'],
    apology: ['对不起', '抱歉', '请原谅'],
    question: ['你好吗？', '有什么新鲜事？', '你从哪里来？'],
    affirmation: ['是的', '当然', '绝对'],
    negation: ['不', '不用谢', '我不知道'],
    introduction: ['我叫...', '我来自...', '很高兴认识你'],
    numbers: ['一二三', '第一第二', '一百一千'],
    time: ['一点了', '三点了', '中午', '午夜'],
    directions: ['向右', '向左', '直走', '转弯'],
    food: ['很好吃', '请慢用', '我饿了', '我渴了'],
    weather: ['晴天', '下雨', '冷', '热'],
    emergency: ['救命！', '报警', '我需要医生'],
    colors: ['红色', '蓝色', '绿色', '黄色', '黑色', '白色'],
    animals: ['狗', '猫', '鸟', '鱼', '马', '牛'],
    transportation: ['汽车', '公共汽车', '火车', '飞机', '船', '自行车'],
    shopping: ['多少钱？', '很贵', '有零钱吗？', '我想买'],
    family: ['母亲', '父亲', '兄弟', '姐妹', '儿子', '女儿'],
    work: ['工作', '办公室', '会议', '老板', '同事', '工资'],
    education: ['学校', '大学', '教授', '学生', '考试', '文凭'],
    health: ['医院', '医生', '药物', '疾病', '健康', '康复'],
  },
  ja: {
    casual: ['やあ', 'おっす', 'よろしく'],
    formal: ['こんにちは、お元気ですか？', 'はじめまして', 'よろしくお願いします'],
    greeting: ['こんにちは', 'おはよう', 'こんばんは'],
    farewell: ['さようなら', 'またね', 'じゃあね'],
    thanks: ['ありがとう', 'ありがとうございます', '感謝します'],
    apology: ['すみません', 'ごめんなさい', '申し訳ありません'],
    question: ['元気ですか？', '何か新しいことは？', 'どこから来ましたか？'],
    affirmation: ['はい', 'もちろん', '絶対に'],
    negation: ['いいえ', '結構です', 'わかりません'],
    introduction: ['...と申します', '...から来ました', 'よろしくお願いします'],
    numbers: ['一二三', '第一第二', '百千'],
    time: ['一時です', '三時です', '正午', '真夜中'],
    directions: ['右へ', '左へ', 'まっすぐ', '曲がる'],
    food: ['美味しい', 'いただきます', 'お腹が空いた', '喉が渇いた'],
    weather: ['晴れ', '雨', '寒い', '暑い'],
    emergency: ['助けて！', '警察を呼んで', '医者が必要です'],
    colors: ['赤', '青', '緑', '黄色', '黒', '白'],
    animals: ['犬', '猫', '鳥', '魚', '馬', '牛'],
    transportation: ['車', 'バス', '電車', '飛行機', '船', '自転車'],
    shopping: ['いくらですか？', '高いですね', 'お釣りは？', '買いたいです'],
    family: ['母', '父', '兄弟', '姉妹', '息子', '娘'],
    work: ['仕事', 'オフィス', '会議', '上司', '同僚', '給料'],
    education: ['学校', '大学', '教授', '学生', '試験', '卒業証書'],
    health: ['病院', '医者', '薬', '病気', '健康', '回復'],
  },
  ko: {
    casual: ['안녕', '반가워', '잘 지내?'],
    formal: ['안녕하세요, 어떻게 지내세요?', '만나서 반갑습니다', '잘 부탁드립니다'],
    greeting: ['안녕하세요', '안녕', '좋은 아침이에요'],
    farewell: ['안녕히 가세요', '다음에 봐요', '잘 가'],
    thanks: ['감사합니다', '고맙습니다', '정말 고마워요'],
    apology: ['죄송합니다', '미안해요', '사과드립니다'],
    question: ['어떻게 지내세요?', '새로운 소식은?', '어디서 오셨어요?'],
    affirmation: ['네', '물론이죠', '확실히'],
    negation: ['아니요', '괜찮습니다', '모르겠습니다'],
    introduction: ['...입니다', '...에서 왔습니다', '만나서 반갑습니다'],
    numbers: ['일이삼', '첫째 둘째', '백 천'],
    time: ['한 시입니다', '세 시입니다', '정오', '자정'],
    directions: ['오른쪽', '왼쪽', '직진', '돌다'],
    food: ['맛있다', '잘 먹겠습니다', '배고프다', '목마르다'],
    weather: ['맑다', '비 온다', '춥다', '덥다'],
    emergency: ['도와주세요!', '경찰 불러주세요', '의사가 필요해요'],
    colors: ['빨간색', '파란색', '초록색', '노란색', '검은색', '흰색'],
    animals: ['개', '고양이', '새', '물고기', '말', '소'],
    transportation: ['자동차', '버스', '기차', '비행기', '배', '자전거'],
    shopping: ['얼마예요?', '너무 비싸네요', '거스름돈 있어요?', '사고 싶어요'],
    family: ['어머니', '아버지', '형제', '자매', '아들', '딸'],
    work: ['일', '사무실', '회의', '상사', '동료', '급여'],
    education: ['학교', '대학교', '교수', '학생', '시험', '졸업장'],
    health: ['병원', '의사', '약', '병', '건강', '회복'],
  },
  ar: {
    casual: ['مرحبا', 'أهلاً', 'هلا'],
    formal: ['السلام عليكم', 'صباح الخير', 'مساء الخير'],
    greeting: ['مرحبا', 'أهلاً وسهلاً', 'كيف حالك؟'],
    farewell: ['مع السلامة', 'إلى اللقاء', 'وداعاً'],
    thanks: ['شكراً', 'شكراً جزيلاً', 'أشكرك'],
    apology: ['أنا آسف', 'عذراً', 'أعتذر'],
    question: ['كيف حالك؟', 'ما الجديد؟', 'من أين أنت؟'],
    affirmation: ['نعم', 'بالتأكيد', 'بالتأكيد'],
    negation: ['لا', 'لا شكراً', 'لا أعرف'],
    introduction: ['اسمي...', 'أنا من...', 'تشرفت بك'],
    numbers: ['واحد اثنان ثلاثة', 'أول ثان', 'مائة ألف'],
    time: ['الساعة الواحدة', 'الساعة الثالثة', 'الظهيرة', 'منتصف الليل'],
    directions: ['يمين', 'يسار', 'استمر', 'انعطف'],
    food: ['لذيذ', 'بصحة', 'أنا جائع', 'أنا عطشان'],
    weather: ['مشمس', 'ممطر', 'بارد', 'حار'],
    emergency: ['ساعدني!', 'اتصل بالشرطة', 'أحتاج طبيب'],
    colors: ['أحمر', 'أزرق', 'أخضر', 'أصفر', 'أسود', 'أبيض'],
    animals: ['كلب', 'قطة', 'طائر', 'سمكة', 'حصان', 'بقرة'],
    transportation: ['سيارة', 'حافلة', 'قطار', 'طائرة', 'سفينة', 'دراجة'],
    shopping: ['كم الثمن؟', 'غالي جداً', 'لديك نقود؟', 'أريد الشراء'],
    family: ['أم', 'أب', 'أخ', 'أخت', 'ابن', 'ابنة'],
    work: ['عمل', 'مكتب', 'اجتماع', 'رئيس', 'زميل', 'راتب'],
    education: ['مدرسة', 'جامعة', 'أستاذ', 'طالب', 'امتحان', 'شهادة'],
    health: ['مستشفى', 'طبيب', 'دواء', 'مرض', 'صحة', 'شفاء'],
  },
  ru: {
    casual: ['Привет', 'Приветик', 'Здорово'],
    formal: ['Здравствуйте', 'Добрый день', 'Очень приятно'],
    greeting: ['Привет', 'Здравствуйте', 'Доброе утро'],
    farewell: ['До свидания', 'Пока', 'До встречи'],
    thanks: ['Спасибо', 'Большое спасибо', 'Благодарю'],
    apology: ['Извините', 'Прошу прощения', 'Мне жаль'],
    question: ['Как дела?', 'Что нового?', 'Откуда вы?'],
    affirmation: ['Да', 'Конечно', 'Безусловно'],
    negation: ['Нет', 'Нет спасибо', 'Я не знаю'],
    introduction: ['Меня зовут...', 'Я из...', 'Очень приятно'],
    numbers: ['Один два три', 'Первый второй', 'Сто тысяча'],
    time: ['Час', 'Три часа', 'Полдень', 'Полночь'],
    directions: ['Направо', 'Налево', 'Прямо', 'Повернуть'],
    food: ['Вкусно', 'Приятного аппетита', 'Я голоден', 'Я хочу пить'],
    weather: ['Солнечно', 'Дождь', 'Холодно', 'Жарко'],
    emergency: ['Помогите!', 'Позвоните в полицию', 'Мне нужен врач'],
    colors: ['Красный', 'Синий', 'Зеленый', 'Желтый', 'Черный', 'Белый'],
    animals: ['Собака', 'Кошка', 'Птица', 'Рыба', 'Лошадь', 'Корова'],
    transportation: ['Машина', 'Автобус', 'Поезд', 'Самолет', 'Корабль', 'Велосипед'],
    shopping: ['Сколько стоит?', 'Очень дорого', 'У вас есть сдача?', 'Я хочу купить'],
    family: ['Мать', 'Отец', 'Брат', 'Сестра', 'Сын', 'Дочь'],
    work: ['Работа', 'Офис', 'Встреча', 'Начальник', 'Коллега', 'Зарплата'],
    education: ['Школа', 'Университет', 'Профессор', 'Студент', 'Экзамен', 'Диплом'],
    health: ['Больница', 'Врач', 'Медицина', 'Болезнь', 'Здоровье', 'Выздоровление'],
  },
};

export const HEALTH_POLL_MS = 3000;
export const STREAM_HEARTBEAT_MS = 2500;
export const STREAM_HEARTBEAT_MAX_MISSES = 2;
export const STREAM_RECONNECT_MS = 1000;
export const STREAM_RECONNECT_MAX_ATTEMPTS = 5;
export const STREAM_RECONNECT_MAX_DELAY_MS = 30000;
export const MAX_AUDIO_SEND_QUEUE = 10;
export const MAX_BUFFERED_AUDIO_CHUNKS = 30;
export const LATENCY_HISTORY_KEY = 'translator_latency_history';
export const LATENCY_HISTORY_LIMIT = 12;
export const LATENCY_TARGET_MS = 1000;
export const VOICE_WARMUP_COOLDOWN_MS = 5 * 60 * 1000;
export const VOICE_PREFETCH_TIMEOUT_MS = 4000;
export const HOLD_TO_TALK_DELAY_MS = 260;
export const EXPECTED_BACKEND_RELEASE = '2026-05-13-active-speaker-v19';
export const FRONTEND_BUILD_ID = 'continuous-interpreter-v29-browser-live-text';
export const EXPERIMENTAL_IOS_STREAMING = true;

// ---------- Persistence ----------

export function readPersistedTargetLanguage() {
  try {
    const stored = localStorage.getItem('targetLanguage');
    if (stored && TARGET_LANGUAGE_OPTIONS.some((o) => o.code === stored)) return stored;
  } catch {}
  return 'es';
}

export function readPersistedSourceLanguage() {
  try {
    const stored = localStorage.getItem('sourceLanguage');
    if (stored && TARGET_LANGUAGE_OPTIONS.some((o) => o.code === stored)) return stored;
  } catch {}
  return 'en';
}

// ---------- Debug logging ----------

export function readDebugFlag() {
  try {
    return import.meta.env.DEV || localStorage.getItem('translator_debug') === '1';
  } catch {
    return import.meta.env.DEV;
  }
}

export function makeDebugLog(enabled) {
  return (...args) => {
    if (enabled) console.debug(...args);
  };
}

// ---------- Latency stats ----------

export function blankLatencyStats() {
  return { mic_to_backend: '-', backend_response: '-', first_audio: '-', end_to_end: '-' };
}

export function formatLatencyValue(value) {
  if (value === null || value === undefined || value === '' || value === '-') return '-';
  if (typeof value === 'number' && Number.isFinite(value)) {
    return `${Math.max(0, Math.round(value))}ms`;
  }
  return String(value);
}

export function readLatencyHistory() {
  try {
    const raw = localStorage.getItem(LATENCY_HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((item) => ({
        total: Number(item.total),
        backend: Number(item.backend),
        audio: Number(item.audio),
        created_at: Number(item.created_at) || Date.now(),
      }))
      .filter((item) => Number.isFinite(item.total) && item.total > 0)
      .slice(-LATENCY_HISTORY_LIMIT);
  } catch {
    return [];
  }
}

export function summarizeLatencyHistory(history) {
  if (!history.length) return { average: null, best: null };
  const totals = history.map((item) => item.total).filter((value) => Number.isFinite(value) && value > 0);
  if (!totals.length) return { average: null, best: null };
  return {
    average: Math.round(totals.reduce((sum, value) => sum + value, 0) / totals.length),
    best: Math.min(...totals),
  };
}

// ---------- Speaker labels ----------

export function fallbackSpeakerLabel(speaker) {
  const value = String(speaker || '').trim();
  if (!value || value === '-') return 'Person';
  const numericId = value.match(/(\d+)$/)?.[1];
  if (numericId) return `Person ${numericId}`;
  return value.replace(/^speaker[-_\s]*/i, 'Person ').trim() || 'Person';
}

// ---------- Browser feature probes ----------

export function isManualInstallBrowser() {
  const userAgent = navigator.userAgent || '';
  const isIos = /iphone|ipad|ipod/i.test(userAgent);
  const isSafari = /safari/i.test(userAgent) && !/chrome|crios|fxios|edg/i.test(userAgent);
  return isIos || isSafari;
}

export function isIosOrSafariRecorder() {
  const userAgent = navigator.userAgent || '';
  const platform = navigator.platform || '';
  const isIos =
    /iphone|ipad|ipod/i.test(userAgent) ||
    (platform === 'MacIntel' && (navigator.maxTouchPoints || 0) > 1);
  const isSafari = /safari/i.test(userAgent) && !/chrome|crios|fxios|edg|edgios/i.test(userAgent);
  return isIos || isSafari;
}

// ---------- Audio recording ----------

export function preferredAudioMimeType() {
  if (!window.MediaRecorder?.isTypeSupported) return '';
  const candidates = isIosOrSafariRecorder()
    ? ['audio/mp4', 'audio/aac', 'audio/mp4;codecs=mp4a.40.2', 'audio/webm;codecs=opus', 'audio/webm']
    : ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/aac', 'audio/ogg;codecs=opus', 'audio/ogg'];
  return candidates.find((mimeType) => MediaRecorder.isTypeSupported(mimeType)) || '';
}

export function createAudioRecorder(stream, audioBitsPerSecond) {
  if (!window.MediaRecorder) {
    window.alert?.('Recording not supported on this device/browser');
    throw new Error('Recording not supported on this device/browser');
  }
  const options = {};
  const mimeType = preferredAudioMimeType();
  if (mimeType) options.mimeType = mimeType;
  if (audioBitsPerSecond) options.audioBitsPerSecond = audioBitsPerSecond;
  try {
    return new MediaRecorder(stream, options);
  } catch (err) {
    console.warn('MediaRecorder rejected options, retrying without explicit mimeType', err);
    return new MediaRecorder(stream);
  }
}

export function audioFileExtension(mimeType) {
  if (mimeType.includes('mp4') || mimeType.includes('aac')) return '.m4a';
  if (mimeType.includes('ogg')) return '.ogg';
  return '.webm';
}

// ---------- Speech recognition ----------

export function speechRecognitionConstructor() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

export function speechRecognitionLanguage(code) {
  const normalized = String(code || 'en').toLowerCase().split(/[-_]/)[0];
  // Map to primary locale, with fallbacks for regional variants
  return (
    {
      en: 'en-US',
      es: 'es-ES',
      'es-MX': 'es-MX',
      'es-AR': 'es-AR',
      ht: 'ht-HT',
      fr: 'fr-FR',
      'fr-CA': 'fr-CA',
      'fr-BE': 'fr-BE',
      'fr-CH': 'fr-CH',
      de: 'de-DE',
      'de-AT': 'de-AT',
      'de-CH': 'de-CH',
      it: 'it-IT',
      'it-CH': 'it-CH',
      pt: 'pt-BR',
      'pt-PT': 'pt-PT',
      zh: 'zh-CN',
      'zh-TW': 'zh-TW',
      'zh-HK': 'zh-HK',
      'zh-Hant': 'zh-TW',
      ja: 'ja-JP',
      ko: 'ko-KR',
      ar: 'ar-SA',
      'ar-EG': 'ar-EG',
      'ar-MA': 'ar-MA',
      'ar-AE': 'ar-AE',
      'ar-TN': 'ar-TN',
      ru: 'ru-RU',
    }[code] || (
      {
        en: 'en-US',
        es: 'es-ES',
        ht: 'ht-HT',
        fr: 'fr-FR',
        de: 'de-DE',
        it: 'it-IT',
        pt: 'pt-BR',
        zh: 'zh-CN',
        ja: 'ja-JP',
        ko: 'ko-KR',
        ar: 'ar-SA',
        ru: 'ru-RU',
      }[normalized] || normalized
    )
  );
}

// ---------- Auth helpers ----------

export function withAuthToken(url, token) {
  if (!token) return url;
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}access_token=${encodeURIComponent(token)}`;
}

export function authHeaders(token, extra = {}) {
  if (!token) return extra;
  return { ...extra, Authorization: `Bearer ${token}` };
}

export async function responseErrorMessage(response, fallback) {
  try {
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const body = await response.json();
      return body.detail || body.message || fallback;
    }
    const text = await response.text();
    return text || fallback;
  } catch {
    return fallback;
  }
}

// ---------- Media / mic errors ----------

export function mediaErrorMessage(error) {
  if (error?.name === 'NotAllowedError') return 'Microphone permission blocked';
  if (error?.name === 'NotFoundError') return 'No microphone found';
  if (error?.name === 'NotSupportedError') return 'Audio recording is not supported in this browser';
  return 'Could not start microphone';
}

export async function requestAudioStream(deviceId) {
  const audioConstraints = {
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
    ...(deviceId ? { deviceId: { exact: deviceId } } : {}),
  };
  try {
    return await navigator.mediaDevices.getUserMedia({ audio: audioConstraints });
  } catch (error) {
    console.warn('Enhanced audio constraints failed, retrying basic audio', error);
    return navigator.mediaDevices.getUserMedia({ audio: deviceId ? { deviceId: { exact: deviceId } } : true });
  }
}

// ---------- Misc text helpers ----------

export function uniqueStrings(values = []) {
  const seen = new Set();
  return values
    .map((value) => String(value || '').trim())
    .filter((value) => {
      if (!value || seen.has(value.toLowerCase())) return false;
      seen.add(value.toLowerCase());
      return true;
    });
}

export function extractBrainPlan(payload = {}) {
  const plan = payload.cip_response_plan || payload.response_plan || null;
  const hints = payload.cip_client_hints || payload.client_hints || plan?.client_hints || {};
  const repairOptions = payload.cip_repair_options || plan?.repair_options || [];
  return {
    plan: plan && typeof plan === 'object' ? plan : null,
    hints: hints && typeof hints === 'object' ? hints : {},
    repairOptions: Array.isArray(repairOptions) ? repairOptions : [],
  };
}

export function compactRepairLabel(option = {}) {
  if (option.type === 'auto_switch_source_language') {
    return `Using ${String(option.language || '').toUpperCase()}`;
  }
  if (option.type === 'switch_source_language') {
    return `Switch to ${String(option.language || '').toUpperCase()}`;
  }
  if (option.type === 'repeat_terms') return 'Repeat exact terms';
  if (option.type === 'confirm_exact') return 'Confirm exact words';
  if (option.type === 'choose_meaning') return `Meaning of ${option.word}`;
  if (option.type === 'repeat_slowly') return 'Repeat slowly';
  if (option.type === 'preserve_code_switch') return 'Keep mixed language';
  return option.label || 'Repair';
}

/**
 * Look up a human-readable language name from a code, falling back
 * through the backend's `languages` map, the local
 * TARGET_LANGUAGE_OPTIONS table, and finally the uppercased code.
 * Prefers native names when available.
 */
export function languageName(code, languages = {}) {
  if (!code) return '';
  const option = TARGET_LANGUAGE_OPTIONS.find((opt) => opt.code === code);
  // Prefer native name if available, otherwise use label or backend mapping
  return (
    languages[code] ||
    option?.label ||
    option?.native ||
    String(code).toUpperCase()
  );
}

/**
 * Get text direction (ltr or rtl) for a language code.
 */
export function languageDirection(code) {
  const option = TARGET_LANGUAGE_OPTIONS.find((opt) => opt.code === code);
  return option?.dir || 'ltr';
}

/**
 * Search/filter languages by query (matches code, label, or native name)
 */
export function searchLanguages(query) {
  if (!query) return TARGET_LANGUAGE_OPTIONS;
  const lowerQuery = String(query).toLowerCase();
  return TARGET_LANGUAGE_OPTIONS.filter((opt) =>
    opt.code.toLowerCase().includes(lowerQuery) ||
    opt.label.toLowerCase().includes(lowerQuery) ||
    opt.native?.toLowerCase().includes(lowerQuery) ||
    opt.family?.toLowerCase().includes(lowerQuery)
  );
}

/**
 * Get TTS voice recommendation for a language code
 */
export function getTTSVoice(code) {
  const option = TARGET_LANGUAGE_OPTIONS.find((opt) => opt.code === code);
  return option?.ttsVoice || null;
}

/**
 * Get currency symbol for a language code
 */
export function getCurrencySymbol(code) {
  const option = TARGET_LANGUAGE_OPTIONS.find((opt) => opt.code === code);
  return option?.currency || '$';
}

/**
 * Format number according to language conventions
 */
export function formatNumber(number, code) {
  const option = TARGET_LANGUAGE_OPTIONS.find((opt) => opt.code === code);
  const locale = option?.code === 'zh' ? 'zh-CN' : 
                 option?.code === 'ja' ? 'ja-JP' :
                 option?.code === 'ko' ? 'ko-KR' :
                 option?.code === 'ar' ? 'ar-SA' :
                 option?.code === 'ru' ? 'ru-RU' :
                 option?.code === 'de' ? 'de-DE' :
                 option?.code === 'fr' ? 'fr-FR' :
                 option?.code === 'es' ? 'es-ES' :
                 option?.code === 'pt' ? 'pt-BR' :
                 option?.code === 'it' ? 'it-IT' :
                 'en-US';
  return new Intl.NumberFormat(locale).format(number);
}

/**
 * Format date/time according to language conventions
 */
export function formatDateTime(date, code, options = {}) {
  const option = TARGET_LANGUAGE_OPTIONS.find((opt) => opt.code === code);
  const locale = option?.code === 'zh' ? 'zh-CN' : 
                 option?.code === 'ja' ? 'ja-JP' :
                 option?.code === 'ko' ? 'ko-KR' :
                 option?.code === 'ar' ? 'ar-SA' :
                 option?.code === 'ru' ? 'ru-RU' :
                 option?.code === 'de' ? 'de-DE' :
                 option?.code === 'fr' ? 'fr-FR' :
                 option?.code === 'es' ? 'es-ES' :
                 option?.code === 'pt' ? 'pt-BR' :
                 option?.code === 'it' ? 'it-IT' :
                 'en-US';
  return new Intl.DateTimeFormat(locale, options).format(date);
}

/**
 * Get measurement unit system for a language (imperial or metric)
 */
export function getMeasurementUnits(code) {
  const option = TARGET_LANGUAGE_OPTIONS.find((opt) => opt.code === code);
  return option?.units || 'metric';
}

/**
 * Get keyboard layout hint for a language
 */
export function getKeyboardLayout(code) {
  const option = TARGET_LANGUAGE_OPTIONS.find((opt) => opt.code === code);
  return option?.keyboard || 'QWERTY';
}

/**
 * Get date format preference for a language (MDY, DMY, YMD)
 */
export function getDateFormat(code) {
  const option = TARGET_LANGUAGE_OPTIONS.find((opt) => opt.code === code);
  return option?.dateFormat || 'MDY';
}

/**
 * Get name ordering preference for a language (firstLast, lastFirst)
 */
export function getNameOrder(code) {
  const option = TARGET_LANGUAGE_OPTIONS.find((opt) => opt.code === code);
  return option?.nameOrder || 'firstLast';
}

/**
 * Format phone number according to language conventions
 */
export function formatPhoneNumber(phone, code) {
  if (!phone) return '';
  const cleaned = phone.replace(/\D/g, '');
  const option = TARGET_LANGUAGE_OPTIONS.find((opt) => opt.code === code);
  
  // US/Canada format
  if (code === 'en' && cleaned.length === 10) {
    return `(${cleaned.slice(0, 3)}) ${cleaned.slice(3, 6)}-${cleaned.slice(6)}`;
  }
  
  // European format (most countries)
  if (['es', 'fr', 'de', 'it', 'pt', 'ru'].includes(code) && cleaned.length >= 10) {
    const groups = cleaned.match(/.{1,2}/g);
    return groups ? groups.join(' ') : phone;
  }
  
  // Default: return cleaned with spaces
  return cleaned.match(/.{1,3}/g)?.join(' ') || phone;
}

/**
 * Format address according to language conventions
 */
export function formatAddress(address, code) {
  if (!address) return '';
  const option = TARGET_LANGUAGE_OPTIONS.find((opt) => opt.code === code);
  
  // Most languages: street, city, postal code, country
  // US: street, city, state postal code
  // Japanese: postal code, prefecture, city, street
  
  if (code === 'ja' || code === 'zh' || code === 'ko') {
    // Asian format: postal code first
    const parts = address.split(',').map(p => p.trim());
    if (parts.length >= 2) {
      return parts.reverse().join(', ');
    }
  }
  
  return address;
}

/**
 * Build a shareable room URL embedding the active session id, then
 * either pop the native share sheet (mobile) or fall back to
 * clipboard copy. Returns the chosen mechanism ("share" | "copy") so
 * the caller can update its status text.
 */
export async function shareRoomUrl({ sessionId, copyToClipboard }) {
  const shareUrl = new URL(window.location.origin);
  shareUrl.searchParams.set('session', sessionId);
  const url = shareUrl.toString();
  const payload = {
    title: 'Anai Translator',
    text: 'Join my live translator room.',
    url,
  };
  try {
    if (navigator.share) {
      await navigator.share(payload);
      return 'share';
    }
    await copyToClipboard(url, 'room');
    return 'copy';
  } catch (error) {
    if (error?.name !== 'AbortError') {
      await copyToClipboard(url, 'room');
    }
    return 'copy';
  }
}

export function activePacketMs({ lowBandwidthMode, streamPacketMs, experimentalIosStreaming }) {
  if (lowBandwidthMode) return 500;
  if (isIosOrSafariRecorder()) return experimentalIosStreaming ? 110 : Math.max(streamPacketMs, 400);
  return Math.min(streamPacketMs, 80);
}

export function isFatalStreamError(message = '') {
  return /quota|too many active|not authorized|unauthorized|forbidden|exceeds|buffer limit/i.test(String(message || ''));
}

export function logAudioStream(stream, debugLog) {
  debugLog('AUDIO STREAM:', stream);
  debugLog('AUDIO TRACKS:', stream.getAudioTracks());
  stream.getAudioTracks().forEach((track) => {
    debugLog('TRACK ENABLED:', track.enabled);
    debugLog('TRACK STATE:', track.readyState);
  });
}

export function base64ToArrayBuffer(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

export function buildTranslatePayload({
  text,
  sourceLanguage,
  targetLanguage,
  sessionId,
  deviceId,
  speakerName,
  speakerMode,
  synthesizeAudio = false,
  audioResponseFormat = null,
  translationMode = null,
  translationProvider = null,
  googleTtsApiKey = null,
}) {
  const body = {
    text,
    source_language: sourceLanguage,
    target_language: targetLanguage,
    synthesize_audio: synthesizeAudio,
    session_id: sessionId,
    device_id: deviceId,
    speaker_name: speakerName,
    speaker_mode: speakerMode,
  };
  if (audioResponseFormat) body.audio_response_format = audioResponseFormat;
  if (translationMode) body.translation_mode = translationMode;
  if (translationProvider) body.translation_provider = translationProvider;
  if (googleTtsApiKey) body.google_tts_api_key = googleTtsApiKey;
  return body;
}
