"""Skill Combo Manager - Handles cooldown tracking and combo execution.

This manager:
- Tracks individual skill cooldowns
- Tracks combo set cooldowns
- Executes combos when all skills are available
- Uses hardware-level inputs via input_controller
- Supports stealth attack mode (randomized between Tab-target + R/T attacks, single skill, combo)
"""
import time
import random
from typing import Dict, Optional, List, Tuple
from loguru import logger
import skill_combo_config
from input_controller import focus_window, tap_key, hold_key
from input_controller import execution_wait


class SkillComboManager:
    """Manages skill combo execution with cooldown tracking."""
    
    def __init__(self, hwnd: int):
        """Initialize the skill combo manager.
        
        Args:
            hwnd: Window handle for the game
        """
        self.hwnd = hwnd
        
        # Cooldown trackers: skill_key -> last_used_time
        self._skill_cooldowns: Dict[str, float] = {}
        
        # Combo cooldown trackers: combo_name -> last_used_time
        self._combo_cooldowns: Dict[str, float] = {}
        
        # Last combo check time (for logging)
        self._last_check_time = 0
        
        # Single skill global cooldown tracker
        self._last_single_skill_use = 0.0
        
        # Validate configuration on init
        if not skill_combo_config.validate_configuration():
            logger.error("Skill combo configuration is invalid!")
        
        logger.info("✓ Skill Combo Manager initialized")
    
    def is_skill_ready(self, skill: str) -> bool:
        """Check if a skill is off cooldown.
        
        Args:
            skill: Skill keybind (e.g., '1', 'alt+2', 'ctrl+5')
        
        Returns:
            True if skill is ready to use, False if on cooldown
        """
        skill_lower = skill.lower()
        cooldown = skill_combo_config.get_skill_cooldown(skill_lower)
        
        if skill_lower not in self._skill_cooldowns:
            return True  # Never used, ready to use
        
        last_used = self._skill_cooldowns[skill_lower]
        time_since_use = time.time() - last_used
        
        return time_since_use >= cooldown
    
    def is_combo_ready(self, combo: Dict) -> bool:
        """Check if a combo set is off cooldown.
        
        Args:
            combo: Combo set dictionary
        
        Returns:
            True if combo cooldown is ready, False if on cooldown
        """
        combo_name = combo.get('name', 'unnamed')
        combo_cooldown = combo.get('cooldown', 60.0)
        
        if combo_name not in self._combo_cooldowns:
            return True  # Never used, ready to use
        
        last_used = self._combo_cooldowns[combo_name]
        time_since_use = time.time() - last_used
        
        return time_since_use >= combo_cooldown
    
    def are_all_skills_ready(self, skills: List[str]) -> bool:
        """Check if all skills in a list are off cooldown.
        
        Args:
            skills: List of skill keybinds
        
        Returns:
            True if all skills are ready, False if any are on cooldown
        """
        for skill in skills:
            if not self.is_skill_ready(skill):
                return False
        return True
    
    def get_skill_cooldown_remaining(self, skill: str) -> float:
        """Get remaining cooldown time for a skill.
        
        Args:
            skill: Skill keybind
        
        Returns:
            Remaining cooldown in seconds (0 if ready)
        """
        skill_lower = skill.lower()
        cooldown = skill_combo_config.get_skill_cooldown(skill_lower)
        
        if skill_lower not in self._skill_cooldowns:
            return 0.0
        
        last_used = self._skill_cooldowns[skill_lower]
        time_since_use = time.time() - last_used
        remaining = cooldown - time_since_use
        
        return max(0.0, remaining)
    
    def get_combo_cooldown_remaining(self, combo: Dict) -> float:
        """Get remaining cooldown time for a combo.
        
        Args:
            combo: Combo set dictionary
        
        Returns:
            Remaining cooldown in seconds (0 if ready)
        """
        combo_name = combo.get('name', 'unnamed')
        combo_cooldown = combo.get('cooldown', 60.0)
        
        if combo_name not in self._combo_cooldowns:
            return 0.0
        
        last_used = self._combo_cooldowns[combo_name]
        time_since_use = time.time() - last_used
        remaining = combo_cooldown - time_since_use
        
        return max(0.0, remaining)
    
    def execute_skill(self, skill: str) -> bool:
        """Execute a single skill using hardware-level input.
        
        Args:
            skill: Skill keybind (e.g., '1', 'alt+2', 'ctrl+5')
        
        Returns:
            True if skill was executed, False if failed
        """
        try:
            # Parse and normalize key (modifiers stripped by config parser)
            _, key = skill_combo_config.parse_skill_keybind(skill)

            # Normalize lookup and cooldown check
            skill_lower = key.lower()
            if not self.is_skill_ready(skill_lower):
                logger.debug(f"Skill '{skill}' (normalized '{skill_lower}') is on cooldown; skipping execution")
                return False

            # Focus game window and send a single key press via interception-only API
            focus_window(self.hwnd)
            tap_key(skill_lower)
            logger.debug(f"Skill executed: {skill_lower}")

            # Mark skill as used
            self._skill_cooldowns[skill_lower] = time.time()
            return True
        except Exception as e:
            logger.error(f"Failed to execute skill '{skill}': {e}")
            return False
    
    def execute_combo(self, combo: Dict) -> bool:
        """Execute a combo set (all skills in sequence).
        
        Args:
            combo: Combo set dictionary
        
        Returns:
            True if combo was executed successfully, False otherwise
        """
        combo_name = combo.get('name', 'unnamed')
        skills = combo.get('skills', [])
        delay = combo.get('delay_between_skills', 0.5)
        
        logger.info(f"Executing combo: {combo_name} ({len(skills)} skills)")
        
        try:
            # Ensure combo and skills are ready before executing
            if not self.is_combo_ready(combo):
                logger.debug(f"Combo '{combo_name}' is on cooldown; skipping execution")
                return False
            if not self.are_all_skills_ready(skills):
                logger.debug(f"Combo '{combo_name}' has skills on cooldown; skipping execution")
                return False

            # Optional pre-macro focus + delay
            pre_focus = combo.get('pre_focus', None)
            if pre_focus is None:
                pre_focus = skill_combo_config.PRE_MACRO_FOCUS_ENABLED

            if pre_focus:
                pre_delay = combo.get('pre_focus_delay', skill_combo_config.PRE_MACRO_FOCUS_DELAY)
                randomized_pre_delay = skill_combo_config.get_randomized_delay(pre_delay)
                logger.debug(f"Pre-focus enabled for combo '{combo_name}': focusing window and waiting {randomized_pre_delay:.2f}s")
                # Focus the game window then wait before starting the combo
                focus_window(self.hwnd)
                execution_wait(randomized_pre_delay)

            for idx, skill in enumerate(skills):
                # Execute the skill (execute_skill now validates per-skill cooldown)
                if not self.execute_skill(skill):
                    logger.warning(f"Combo '{combo_name}' interrupted at skill {idx+1}/{len(skills)}")
                    return False

                # Wait between skills (except after the last one)
                if idx < len(skills) - 1:
                    randomized_delay = skill_combo_config.get_randomized_delay(delay)
                    logger.debug(f"Delay {randomized_delay:.2f}s before next skill")
                    execution_wait(randomized_delay)

            # Mark combo as used
            self._combo_cooldowns[combo_name] = time.time()

            logger.success(f"✓ Combo '{combo_name}' executed successfully")
            return True

        except Exception as e:
            logger.error(f"Error executing combo '{combo_name}': {e}")
            return False
    
    def try_execute_combos(self) -> bool:
        """Try to execute any available combo.
        
        Checks all enabled combos in priority order and executes the first one
        that is ready (all skills off cooldown and combo cooldown ready).
        
        Returns:
            True if a combo was executed, False if none were ready
        """
        if not skill_combo_config.SKILL_COMBO_ENABLED:
            return False
        
        # Get enabled combos in priority order
        combos = skill_combo_config.get_enabled_combo_sets()
        
        if not combos:
            return False
        
        # Try each combo in order
        for combo in combos:
            combo_name = combo.get('name', 'unnamed')
            skills = combo.get('skills', [])
            
            # Check if combo cooldown is ready
            if not self.is_combo_ready(combo):
                combo_cd_remaining = self.get_combo_cooldown_remaining(combo)
                logger.debug(f"Combo '{combo_name}' on cooldown: {combo_cd_remaining:.1f}s remaining")
                continue
            
            # Check if all skills are ready
            if not self.are_all_skills_ready(skills):
                # Find which skills are on cooldown
                skills_on_cd = []
                for skill in skills:
                    if not self.is_skill_ready(skill):
                        cd_remaining = self.get_skill_cooldown_remaining(skill)
                        skills_on_cd.append(f"{skill}({cd_remaining:.1f}s)")
                logger.debug(f"Combo '{combo_name}' waiting for skills: {', '.join(skills_on_cd)}")
                continue
            
            # Combo is ready! Execute it
            logger.info(f"⚡ Combo '{combo_name}' ready - executing!")
            return self.execute_combo(combo)
        
        # No combos were ready
        return False

    def get_ready_combos(self) -> List[Dict]:
        """Return a list of enabled combos that are ready now.

        A combo is considered ready if:
        - The combo's own cooldown has expired, and
        - All of its skills are currently off cooldown.

        Returns:
            A list of combo dicts that are ready to execute.
        """
        if not skill_combo_config.SKILL_COMBO_ENABLED:
            return []

        combos = skill_combo_config.get_enabled_combo_sets()
        ready: List[Dict] = []
        for combo in combos:
            if not self.is_combo_ready(combo):
                continue
            skills = combo.get('skills', [])
            if self.are_all_skills_ready(skills):
                ready.append(combo)
        return ready

    def try_execute_random_combo(self) -> bool:
        """Pick a random ready combo and execute it.

        Returns:
            True if a combo was executed, False otherwise.
        """
        ready = self.get_ready_combos()
        if not ready:
            return False

        combo = random.choice(ready)
        logger.info(f"⚡ Random combo selected: {combo.get('name','unnamed')}")
        return self.execute_combo(combo)
    
    def get_status_summary(self) -> str:
        """Get a summary of all combo and skill cooldown statuses.
        
        Returns:
            Formatted string with cooldown information
        """
        lines = []
        lines.append("=== Skill Combo Status ===")
        
        combos = skill_combo_config.get_enabled_combo_sets()
        for combo in combos:
            combo_name = combo.get('name', 'unnamed')
            combo_cd = self.get_combo_cooldown_remaining(combo)
            
            if combo_cd > 0:
                status = f"⏱ Cooldown: {combo_cd:.1f}s"
            else:
                skills = combo.get('skills', [])
                if self.are_all_skills_ready(skills):
                    status = "✅ READY"
                else:
                    skills_on_cd = []
                    for skill in skills:
                        if not self.is_skill_ready(skill):
                            cd = self.get_skill_cooldown_remaining(skill)
                            skills_on_cd.append(f"{skill}({cd:.1f}s)")
                    status = f"⏳ Waiting: {', '.join(skills_on_cd)}"
            
            lines.append(f"  {combo_name}: {status}")
        
        return '\n'.join(lines)
    
    def reset_cooldowns(self):
        """Reset all cooldowns (for testing/debugging)."""
        self._skill_cooldowns.clear()
        self._combo_cooldowns.clear()
        self._last_single_skill_use = 0.0
        logger.info("All cooldowns reset")

    # ------------------------------
    # Readiness helpers
    # ------------------------------

    def available_single_skills(self) -> List[str]:
        """Return list of skills from pool that are currently off cooldown.

        Respects SINGLE_SKILL_POOL (or all skills if empty) and per-skill cooldowns.
        Does not consider the global single skill cooldown (GCD).
        """
        pool = skill_combo_config.SINGLE_SKILL_POOL or list(skill_combo_config.SKILL_COOLDOWNS.keys())
        return [s for s in pool if self.is_skill_ready(s)]

    def has_available_single_skill(self) -> bool:
        """True if GCD is ready and at least one pool skill is off cooldown."""
        if not self.is_single_skill_ready():
            return False
        return len(self.available_single_skills()) > 0

    def has_ready_combo(self) -> bool:
        """True if at least one enabled combo is fully ready now."""
        return len(self.get_ready_combos()) > 0
    
    def choose_attack_mode(self) -> str:
        """Choose attack mode based on stealth configuration.
        
        Returns:
            'standard_attack', 'single_skill', or 'combo_set'
        """
        if not skill_combo_config.STEALTH_ATTACK_MODE_ENABLED:
            return 'combo_set'  # Default to combo execution
        
        weights = skill_combo_config.ATTACK_MODE_WEIGHTS
        modes = list(weights.keys())
        probabilities = list(weights.values())
        
        # Normalize probabilities
        total = sum(probabilities)
        if total != 1.0:
            probabilities = [p / total for p in probabilities]
        
        chosen = random.choices(modes, weights=probabilities, k=1)[0]
        return chosen

    def choose_actionable_mode(self, has_health: bool) -> str:
        """Choose an attack mode using weights but ensure it's actionable.

        Filters choices by readiness (available skills/ready combos). If no weighted choice is actionable,
        falls back in this order: single_skill -> combo_set -> standard_attack, preferring modes that are
        executable at this moment.
        """

        # Gather readiness
        single_ready = self.has_available_single_skill()
        combo_ready = self.has_ready_combo()

        # Build weighted candidate list conditioned on readiness
        weights = skill_combo_config.ATTACK_MODE_WEIGHTS.copy()
        candidates: List[Tuple[str, float]] = []
        for mode, w in weights.items():
            if mode == 'single_skill' and not single_ready:
                continue
            if mode == 'combo_set' and not combo_ready:
                continue
            candidates.append((mode, max(0.0, float(w))))

        if candidates:
            modes, probs = zip(*candidates)
            total = sum(probs)
            if total <= 0:
                modes = ('single_skill', 'combo_set', 'standard_attack')
                probs = (1, 1, 1)
            choice = random.choices(modes, weights=probs, k=1)[0]
            return choice

        # No weighted candidate is ready; pick best available fallback
        if single_ready:
            return 'single_skill'
        if combo_ready:
            return 'combo_set'
        return 'standard_attack'
    
    def is_single_skill_ready(self) -> bool:
        """Check if single skill global cooldown is ready.
        
        Returns:
            True if can use single skill, False if on GCD
        """
        gcd = skill_combo_config.SINGLE_SKILL_GLOBAL_COOLDOWN
        time_since_use = time.time() - self._last_single_skill_use
        return time_since_use >= gcd
    
    def execute_single_skill(self) -> bool:
        """Execute a single random skill from the pool.
        
        Returns:
            True if skill was executed, False otherwise
        """
        if not self.is_single_skill_ready():
            logger.debug("Single skill on global cooldown")
            return False
        
        # Get skill pool
        skill_pool = skill_combo_config.SINGLE_SKILL_POOL
        if not skill_pool:
            # If pool is empty, use all configured skills
            skill_pool = list(skill_combo_config.SKILL_COOLDOWNS.keys())
        
        # Filter to only skills that are off cooldown
        available_skills = [s for s in skill_pool if self.is_skill_ready(s)]
        
        if not available_skills:
            logger.debug("No skills available in single skill pool")
            return False
        
        # Pick a random skill
        skill = random.choice(available_skills)
        
        logger.info(f"⚡ Single skill attack: {skill}")
        
        # Execute the skill
        if self.execute_skill(skill):
            self._last_single_skill_use = time.time()
            return True
        
        return False
    
    def try_stealth_attack(self, has_health: bool) -> Tuple[str, bool]:
        """Try to execute an attack using stealth mode.
        
        Args:
            has_health: Retained for compatibility; health detection no longer gates skill usage
        
        Returns:
            (attack_mode, success) tuple
            attack_mode: 'standard_attack', 'single_skill', or 'combo_set'
            success: True if action was taken
        """
        # Always prioritise ready combos so they fire exactly on cooldown
        if self.has_ready_combo():
            logger.debug("Attempting combo execution (combo ready)")
            if self.try_execute_combos():
                return ('combo_set', True)

        # If no combo fired, try a single skill next
        if self.has_available_single_skill():
            logger.debug("Attempting single skill execution (skill ready)")
            if self.execute_single_skill():
                return ('single_skill', True)

        # Optional stealth weighting still allows additional attempts, but should not
        # prevent combos/skills from running as soon as they are ready.
        if skill_combo_config.STEALTH_ATTACK_MODE_ENABLED:
            mode = self.choose_actionable_mode(has_health)
            if mode == 'combo_set':
                logger.debug("Weighted selection chose combo_set; attempting execution")
                if self.try_execute_combos():
                    return ('combo_set', True)
            elif mode == 'single_skill':
                logger.debug("Weighted selection chose single_skill; attempting execution")
                if self.execute_single_skill():
                    return ('single_skill', True)

        # Nothing executed – fall back to standard attacks handled by the planner
        return ('standard_attack', False)
