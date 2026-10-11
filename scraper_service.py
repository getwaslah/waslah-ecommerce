// ==========================================
// Waslah Main Backend (Node.js + Express)
// الخادم الرئيسي لربط الواجهات بقاعدة البيانات والسكريبت
// ==========================================

require('dotenv').config();
const express = require('express');
const cors = require('cors');
const { Pool } = require('pg');
const axios = require('axios'); // للتواصل مع خادم بايثون

const app = express();
const port = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());

// إعداد الاتصال بقاعدة بيانات PostgreSQL
const pool = new Pool({
    user: process.env.DB_USER || 'postgres',
    host: process.env.DB_HOST || 'localhost',
    database: process.env.DB_NAME || 'waslah_db',
    password: process.env.DB_PASSWORD || 'password',
    port: process.env.DB_PORT || 5432,
});

// ==========================================
// API Endpoints (النقاط البرمجية)
// ==========================================

// 1. مسار إنشاء الطلب (يستقبل الرابط من index.html)
app.post('/api/orders/create', async (req, res) => {
    const { url, userId } = req.body;

    if (!url) {
        return res.status(400).json({ error: 'يرجى إرسال رابط المنتج' });
    }

    try {
        // الخطوة أ: إرسال الرابط لمحرك بايثون لجلبه (Scraping)
        const scraperResponse = await axios.post('http://localhost:8000/api/scrape', { url: url });
        const productData = scraperResponse.data;

        // الخطوة ب: جلب أسعار الصرف وإعدادات العمولة من قاعدة البيانات
        const settingsQuery = await pool.query('SELECT * FROM system_settings WHERE id = 1');
        const settings = settingsQuery.rows[0];

        // الخطوة ج: الحساب المالي (الريال اليمني القديم كافتراضي)
        const basePriceYer = productData.price_usd * settings.usd_to_yer_old;
        const waslahFee = basePriceYer * (settings.waslah_commission_percent / 100);
        const totalPriceYer = basePriceYer + waslahFee + settings.shipping_rate_per_kg;

        // الخطوة د: حفظ الطلب في قاعدة البيانات
        const insertOrder = `
            INSERT INTO orders (user_id, store_id, product_url, product_name, product_image_url, original_price_usd, exchange_rate_used, waslah_fee_yer, total_price_yer)
            VALUES ($1, (SELECT id FROM supported_stores WHERE store_name = $2 LIMIT 1), $3, $4, $5, $6, $7, $8, $9)
            RETURNING id, product_name, total_price_yer;
        `;
        
        // (افتراض أن user_id = 1 للمرحلة التجريبية)
        const orderResult = await pool.query(insertOrder, [
            userId || 1, 
            productData.store_name, 
            url, 
            productData.product_name, 
            productData.image_url, 
            productData.price_usd, 
            settings.usd_to_yer_old, 
            waslahFee, 
            totalPriceYer
        ]);

        // الخطوة هـ: إرجاع النتيجة للواجهة الأمامية
        res.status(200).json({
            message: 'تم تحليل الطلب وحفظه بنجاح',
            order_details: orderResult.rows[0],
            scraped_data: productData
        });

    } catch (error) {
        console.error('Error processing order:', error.message);
        res.status(500).json({ error: 'حدث خطأ أثناء معالجة الطلب.' });
    }
});

// 2. مسار رفع السند المالي (يستقبل من checkout.html)
app.post('/api/finance/upload-receipt', async (req, res) => {
    // هنا يتم برمجة استلام الصورة (عبر Multer مثلاً) وحفظها في AWS S3
    // وتحديث حالة الطلب في قاعدة البيانات إلى 'REVIEWING_RECEIPT'
    res.status(200).json({ message: 'تم استلام السند بنجاح وبانتظار المراجعة' });
});

// تشغيل خادم Node.js
app.listen(port, () => {
    console.log(`🚀 Waslah Backend Server is running on port ${port}`);
});