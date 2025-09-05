# assets/ai_services.py
import json
import logging
import re
from typing import Dict, List, Optional

import nltk
import openai  # pip install openai
from PIL import Image
from django.conf import settings
from django.core.files.storage import default_storage
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from transformers import pipeline, AutoModelForCausalLM, AutoTokenizer

logger = logging.getLogger(__name__)

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')


# =======================
# Initialize Transformers pipeline once
# =======================
try:
    TEXT_CLASSIFIER_PIPELINE = pipeline(
        "text-classification",
        model="microsoft/DialoGPT-medium",
        return_all_scores=True
    )
except Exception as e:
    logger.warning(f"Could not load text classifier: {e}")
    TEXT_CLASSIFIER_PIPELINE = None


class AssetCategorizationService:
    """AI-powered asset categorization and analysis service"""

    def __init__(self):
        self.stop_words = set(stopwords.words('english'))
        self.category_keywords = {
            'desktop': [
                'desktop', 'pc', 'workstation', 'tower', 'mini-pc', 'all-in-one',
                'computer', 'cpu', 'motherboard', 'ram', 'memory', 'hard drive',
                'ssd', 'graphics card', 'gpu', 'power supply'
            ],
            'laptop': [
                'laptop', 'notebook', 'ultrabook', 'netbook', 'chromebook',
                'macbook', 'thinkpad', 'portable', 'mobile workstation',
                'gaming laptop', 'business laptop'
            ],
            'server': [
                'server', 'rack server', 'blade server', 'tower server',
                'database server', 'web server', 'file server', 'mail server',
                'application server', 'virtual server', 'hypervisor'
            ],
            'network': [
                'router', 'switch', 'hub', 'firewall', 'access point',
                'wifi', 'ethernet', 'lan', 'wan', 'vpn', 'gateway',
                'modem', 'bridge', 'load balancer', 'network device'
            ],
            'printer': [
                'printer', 'inkjet', 'laser', 'multifunction', 'mfp',
                'scanner', 'copier', 'fax', 'plotter', '3d printer',
                'thermal printer', 'dot matrix'
            ],
            'monitor': [
                'monitor', 'display', 'screen', 'lcd', 'led', 'oled',
                'crt', 'touchscreen', 'dual monitor', 'ultra-wide',
                '4k', 'gaming monitor', 'professional display'
            ],
            'ups': [
                'ups', 'uninterruptible power supply', 'battery backup',
                'power protection', 'surge protector', 'line conditioner',
                'power management'
            ],
            'peripheral': [
                'keyboard', 'mouse', 'webcam', 'microphone', 'speakers',
                'headset', 'joystick', 'gamepad', 'drawing tablet',
                'external hard drive', 'usb hub', 'dock'
            ]
        }

        # Use preloaded Transformers pipeline
        self.text_classifier = TEXT_CLASSIFIER_PIPELINE

        # Initialize OpenAI (if API key is provided)
        if hasattr(settings, 'OPENAI_API_KEY'):
            openai.api_key = settings.OPENAI_API_KEY

    # =======================
    # Main categorization method
    # =======================
    def categorize_asset(self, name: str, description: str = "",
                         specifications: str = "", manufacturer: str = "",
                         model: str = "", image_path: str = None) -> Dict:
        result = {
            'category': 'other',
            'confidence': 0.0,
            'reasoning': 'Unable to determine category',
            'suggestions': [],
            'extracted_specs': {}
        }

        try:
            # Combine all text information
            full_text = f"{name} {description} {specifications} {manufacturer} {model}".strip()

            # Method 1: Keyword-based classification
            keyword_result = self._keyword_based_classification(full_text)

            # Method 2: Machine learning classification (Transformers)
            ml_result = self._ml_based_classification(full_text)

            # Method 3: OpenAI classification (if available)
            openai_result = self._openai_classification(full_text)

            # Method 4: Image analysis (if image provided)
            image_result = None
            if image_path:
                image_result = self._image_based_classification(image_path)

            # Combine results with weighted voting
            final_result = self._combine_classification_results(
                keyword_result, ml_result, openai_result, image_result
            )

            # Extract technical specifications
            final_result['extracted_specs'] = self._extract_specifications(full_text)

            # Generate suggestions
            final_result['suggestions'] = self._generate_suggestions(
                final_result['category'], full_text
            )

            return final_result

        except Exception as e:
            logger.error(f"Asset categorization failed: {e}")
            return result

    # =======================
    # Keyword-based classification
    # =======================
    def _keyword_based_classification(self, text: str) -> Dict:
        text_lower = text.lower()
        tokens = [word for word in word_tokenize(text_lower)
                  if word.isalnum() and word not in self.stop_words]
        category_scores = {}
        for category, keywords in self.category_keywords.items():
            score = 0
            matched_keywords = []
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in text_lower:
                    score += 10
                    matched_keywords.append(keyword)
                for token in tokens:
                    if keyword_lower in token or token in keyword_lower:
                        score += 5
            if score > 0:
                category_scores[category] = {
                    'score': score,
                    'matched_keywords': matched_keywords
                }
        if not category_scores:
            return {'category': 'other', 'confidence': 0.1, 'reasoning': 'No keywords matched'}
        best_category = max(category_scores.keys(), key=lambda k: category_scores[k]['score'])
        max_score = category_scores[best_category]['score']
        confidence = min(0.9, max(0.1, max_score / 50))
        reasoning = f"Keyword matching found: {', '.join(category_scores[best_category]['matched_keywords'])}"
        return {
            'category': best_category,
            'confidence': confidence,
            'reasoning': reasoning
        }

    # =======================
    # ML-based classification (Transformers)
    # =======================
    def _ml_based_classification(self, text: str) -> Optional[Dict]:
        if not self.text_classifier:
            return None
        try:
            classification_prompt = f"This IT equipment description: '{text}' is most likely a:"
            result = self.text_classifier(classification_prompt)
            return {
                'category': 'other',  # Placeholder mapping
                'confidence': 0.5,
                'reasoning': 'ML classification (placeholder)'
            }
        except Exception as e:
            logger.error(f"ML classification failed: {e}")
            return None

    # =======================
    # OpenAI classification
    # =======================
    def _openai_classification(self, text: str) -> Optional[Dict]:
        if not hasattr(settings, 'OPENAI_API_KEY') or not settings.OPENAI_API_KEY:
            return None
        try:
            prompt = f"""
            Analyze this IT equipment description and categorize it:

            Description: "{text}"

            Categories to choose from:
            - desktop: Desktop computers, workstations, PCs
            - laptop: Laptops, notebooks, portable computers
            - server: Servers, rack systems, enterprise systems
            - network: Routers, switches, network equipment
            - printer: Printers, multifunction devices, scanners
            - monitor: Displays, screens, monitors
            - ups: Power supplies, UPS systems, power management
            - peripheral: Keyboards, mice, accessories
            - other: Other equipment not fitting above categories

            Respond with JSON only:
            {{
                "category": "category_name",
                "confidence": 0.85,
                "reasoning": "explanation of why this category was chosen"
            }}
            """
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an IT equipment classification expert."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.1
            )
            result_text = response.choices[0].message.content.strip()
            result = json.loads(result_text)
            if result.get('category') in self.category_keywords.keys() or result.get('category') == 'other':
                return result
            else:
                return {'category': 'other', 'confidence': 0.1, 'reasoning': 'Invalid category from OpenAI'}
        except Exception as e:
            logger.error(f"OpenAI classification failed: {e}")
            return None

    # =======================
    # Image-based classification
    # =======================
    def _image_based_classification(self, image_path: str) -> Optional[Dict]:
        try:
            if default_storage.exists(image_path):
                with default_storage.open(image_path, 'rb') as img_file:
                    img = Image.open(img_file)
                return {
                    'category': 'other',  # Placeholder
                    'confidence': 0.3,
                    'reasoning': 'Image analysis (placeholder implementation)'
                }
        except Exception as e:
            logger.error(f"Image classification failed: {e}")
            return None

    # =======================
    # Combine results
    # =======================
    def _combine_classification_results(self, keyword_result: Dict,
                                        ml_result: Optional[Dict],
                                        openai_result: Optional[Dict],
                                        image_result: Optional[Dict]) -> Dict:
        weights = {
            'keyword': 0.3,
            'ml': 0.2,
            'openai': 0.4,
            'image': 0.1
        }
        category_scores = {}
        reasoning_parts = []
        if keyword_result:
            cat = keyword_result['category']
            score = keyword_result['confidence'] * weights['keyword']
            category_scores[cat] = category_scores.get(cat, 0) + score
            reasoning_parts.append(f"Keywords: {keyword_result['reasoning']}")
        if ml_result:
            cat = ml_result['category']
            score = ml_result['confidence'] * weights['ml']
            category_scores[cat] = category_scores.get(cat, 0) + score
            reasoning_parts.append(f"ML: {ml_result['reasoning']}")
        if openai_result:
            cat = openai_result['category']
            score = openai_result['confidence'] * weights['openai']
            category_scores[cat] = category_scores.get(cat, 0) + score
            reasoning_parts.append(f"AI: {openai_result['reasoning']}")
        if image_result:
            cat = image_result['category']
            score = image_result['confidence'] * weights['image']
            category_scores[cat] = category_scores.get(cat, 0) + score
            reasoning_parts.append(f"Image: {image_result['reasoning']}")
        if category_scores:
            best_category = max(category_scores.keys(), key=lambda k: category_scores[k])
            confidence = category_scores[best_category]
            return {
                'category': best_category,
                'confidence': min(0.95, confidence),
                'reasoning': '; '.join(reasoning_parts)
            }
        return {
            'category': 'other',
            'confidence': 0.1,
            'reasoning': 'No classification methods provided valid results'
        }

    # =======================
    # Extract specifications
    # =======================
    def _extract_specifications(self, text: str) -> Dict:
        specs = {}
        text_lower = text.lower()
        # RAM
        ram_pattern = r'(\d+)\s*(gb|mb)\s*(ram|memory|ddr\d?)'
        ram_match = re.search(ram_pattern, text_lower)
        if ram_match:
            amount, unit = int(ram_match.group(1)), ram_match.group(2)
            specs['ram_gb'] = amount if unit == 'gb' else amount / 1024
        # Storage
        storage_patterns = [
            r'(\d+)\s*(tb|gb)\s*(ssd|solid state)',
            r'(\d+)\s*(tb|gb)\s*(hdd|hard drive|hard disk)',
            r'(\d+)\s*(tb|gb)\s*storage'
        ]
        for pattern in storage_patterns:
            storage_match = re.search(pattern, text_lower)
            if storage_match:
                amount = int(storage_match.group(1))
                unit = storage_match.group(2)
                storage_type = storage_match.group(3)
                storage_gb = amount * 1000 if unit == 'tb' else amount
                if 'ssd' in storage_type or 'solid state' in storage_type:
                    specs['ssd_gb'] = storage_gb
                else:
                    specs['hdd_gb'] = storage_gb
                break
        # CPU
        cpu_patterns = [
            r'(intel|amd)\s+(core\s+i\d|ryzen\s+\d|xeon|athlon)',
            r'(\d+)\s*(ghz|mhz)\s*(processor|cpu)',
            r'(\d+)[-\s]core\s+(processor|cpu)'
        ]
        for pattern in cpu_patterns:
            cpu_match = re.search(pattern, text_lower)
            if cpu_match:
                specs['cpu_info'] = cpu_match.group(0)
                break
        # Screen
        screen_pattern = r'(\d+(?:\.\d+)?)["\s]*(inch|in)\s*(monitor|display|screen)'
        screen_match = re.search(screen_pattern, text_lower)
        if screen_match:
            specs['screen_size_inches'] = float(screen_match.group(1))
        # Network
        network_pattern = r'(\d+)\s*(gbps|mbps|gbit|mbit)'
        network_match = re.search(network_pattern, text_lower)
        if network_match:
            speed = int(network_match.group(1))
            unit = network_match.group(2)
            if 'gb' in unit:
                specs['network_speed_gbps'] = speed
            else:
                specs['network_speed_mbps'] = speed
        return specs

    # =======================
    # Generate suggestions
    # =======================
    def _generate_suggestions(self, category: str, text: str) -> List[str]:
        suggestions = []
        text_lower = text.lower()
        if category == 'desktop':
            suggestions.extend([
                "Consider enabling remote monitoring for performance tracking",
                "Schedule regular maintenance and updates",
                "Monitor temperature and hardware health"
            ])
        elif category == 'laptop':
            suggestions.extend([
                "Track battery health and replacement cycles",
                "Implement mobile device management (MDM)",
                "Consider theft protection and encryption"
            ])
        elif category == 'server':
            suggestions.extend([
                "Enable comprehensive monitoring and alerting",
                "Implement backup and disaster recovery procedures",
                "Monitor resource utilization and capacity planning"
            ])
        elif category == 'network':
            suggestions.extend([
                "Monitor network traffic and performance",
                "Implement security monitoring and intrusion detection",
                "Track configuration changes and firmware updates"
            ])
        elif category == 'printer':
            suggestions.extend([
                "Monitor ink/toner levels and usage",
                "Track maintenance cycles and service history",
                "Consider print quota management"
            ])
        if 'warranty' in text_lower:
            suggestions.append("Set up warranty expiration alerts")
        if any(word in text_lower for word in ['critical', 'important', 'production']):
            suggestions.append("Consider higher priority maintenance scheduling")
        if 'old' in text_lower or 'legacy' in text_lower:
            suggestions.append("Plan for replacement or upgrade")
        return suggestions[:5]  # Limit to 5 suggestions


# =======================
# Auto-categorize Equipment model integration
# =======================
def auto_categorize_equipment(equipment_id: int) -> Dict:
    from .models import Equipment
    try:
        equipment = Equipment.objects.get(id=equipment_id)
        service = AssetCategorizationService()
        image_path = None  # Optional: link to Equipment image field
        result = service.categorize_asset(
            name=equipment.name,
            description=equipment.specifications or "",
            manufacturer=equipment.manufacturer,
            model=equipment.model,
            image_path=image_path
        )
        if result['confidence'] > 0.7:
            equipment.category = result['category']
            equipment.save()
            logger.info(f"Auto-categorized equipment {equipment.id} as {result['category']} "
                        f"with {result['confidence']:.2f} confidence")
        return result
    except Equipment.DoesNotExist:
        return {'error': 'Equipment not found'}
    except Exception as e:
        logger.error(f"Auto-categorization failed for equipment {equipment_id}: {e}")
        return {'error': str(e)}
